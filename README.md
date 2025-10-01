# nginx.sh

Dataset : https://drive.google.com/file/d/1C9_U4711gWrU3dgAJ8bs4Cktn28NOI9s/view?usp=sharing


Controller.py
# controller_lstm_ryu.py
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub

import switch
from datetime import datetime

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, MinMaxScaler
from sklearn.metrics import confusion_matrix, accuracy_score
import joblib
import os
import traceback

# Keras / TensorFlow
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import LSTM, Dense, Dropout

class SimpleMonitor13(switch.SimpleSwitch13):

    def __init__(self, *args, **kwargs):
        super(SimpleMonitor13, self).__init__(*args, **kwargs)
        self.datapaths = {}
        self.monitor_thread = hub.spawn(self._monitor)

        # tempat menyimpan model / scaler / encoder
        self.flow_model = None
        self.scaler = None
        self.le = None
        self.timesteps = 1
        self.features = None

        # spawn training agar tidak block startup
        hub.spawn(self._maybe_train_on_startup)

    def _maybe_train_on_startup(self):
        """
        Jika model sudah ada di disk, muat dulu. Jika tidak ada, lakukan training.
        Hal ini mencegah pelatihan yang tidak perlu setiap kali controller restart.
        """
        try:
            model_path = "flow_model.h5"
            scaler_path = "flow_scaler.save"
            le_path = "flow_le.save"

            if os.path.exists(model_path) and os.path.exists(scaler_path) and os.path.exists(le_path):
                # load existing
                try:
                    self.flow_model = load_model(model_path)
                    self.scaler = joblib.load(scaler_path)
                    self.le = joblib.load(le_path)
                    # features cannot be inferred reliably here; set to None but will be inferred during predict
                    self.timesteps = 1
                    self.logger.info("Loaded existing LSTM model and preprocessing objects.")
                except Exception:
                    self.logger.exception("Gagal load model/scaler/labelencoder, akan melakukan training ulang.")
                    self.flow_training()
            else:
                # lakukan training jika belum ada model
                self.flow_training()
        except Exception:
            self.logger.exception("Error di _maybe_train_on_startup")

    @set_ev_cls(ofp_event.EventOFPStateChange,
                [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if datapath.id not in self.datapaths:
                self.logger.debug('register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.debug('unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]

    def _monitor(self):
        while True:
            for dp in self.datapaths.values():
                self._request_stats(dp)
            hub.sleep(10)
            # prediksi tiap 10 detik
            self.flow_predict()

    def _request_stats(self, datapath):
        self.logger.debug('send stats request: %016x', datapath.id)
        parser = datapath.ofproto_parser

        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):

        timestamp = datetime.now().timestamp()

        # gunakan mode append, tapi sebelumnya file diinisialisasi header di tempat lain
        # untuk menghindari race condition, kita tulis seluruh file setiap kali (sebagai pendekatan sederhana)
        file0 = open("PredictFlowStatsfile.csv","w")
        file0.write('timestamp,datapath_id,flow_id,ip_src,tp_src,ip_dst,tp_dst,ip_proto,icmp_code,icmp_type,flow_duration_sec,flow_duration_nsec,idle_timeout,hard_timeout,flags,packet_count,byte_count,packet_count_per_second,packet_count_per_nsecond,byte_count_per_second,byte_count_per_nsecond\n')
        body = ev.msg.body
        icmp_code = -1
        icmp_type = -1
        tp_src = 0
        tp_dst = 0

        for stat in sorted([flow for flow in body if (flow.priority == 1) ], key=lambda flow:
            (flow.match.get('eth_type',0),flow.match.get('ipv4_src',''),flow.match.get('ipv4_dst',''),flow.match.get('ip_proto',0))):
        
            ip_src = stat.match.get('ipv4_src', '0.0.0.0')
            ip_dst = stat.match.get('ipv4_dst', '0.0.0.0')
            ip_proto = stat.match.get('ip_proto', 0)
            
            if ip_proto == 1:
                icmp_code = stat.match.get('icmpv4_code', -1)
                icmp_type = stat.match.get('icmpv4_type', -1)
                
            elif ip_proto == 6:
                tp_src = stat.match.get('tcp_src', 0)
                tp_dst = stat.match.get('tcp_dst', 0)

            elif ip_proto == 17:
                tp_src = stat.match.get('udp_src', 0)
                tp_dst = stat.match.get('udp_dst', 0)

            flow_id = str(ip_src) + str(tp_src) + str(ip_dst) + str(tp_dst) + str(ip_proto)
          
            try:
                packet_count_per_second = stat.packet_count / stat.duration_sec
                packet_count_per_nsecond = stat.packet_count / stat.duration_nsec
            except Exception:
                packet_count_per_second = 0
                packet_count_per_nsecond = 0
                
            try:
                byte_count_per_second = stat.byte_count / stat.duration_sec
                byte_count_per_nsecond = stat.byte_count / stat.duration_nsec
            except Exception:
                byte_count_per_second = 0
                byte_count_per_nsecond = 0
                
            file0.write("{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\n"
                .format(timestamp, ev.msg.datapath.id, flow_id, ip_src, tp_src, ip_dst, tp_dst,
                        ip_proto, icmp_code, icmp_type,
                        stat.duration_sec, stat.duration_nsec,
                        stat.idle_timeout, stat.hard_timeout,
                        stat.flags if hasattr(stat, 'flags') else 0, stat.packet_count, stat.byte_count,
                        packet_count_per_second, packet_count_per_nsecond,
                        byte_count_per_second, byte_count_per_nsecond))
            
        file0.close()

    def flow_training(self):
        """
        Training LSTM menggunakan FlowStatsfile.csv.
        Menyimpan model (flow_model.h5), scaler (flow_scaler.save), dan label encoder (flow_le.save).
        """
        try:
            self.logger.info("Flow Training (LSTM) dimulai ...")
            # 1. Load dataset
            flow_dataset = pd.read_csv('FlowStatsfile.csv')

            # 2. Simpan kolom ip_dst jika ingin digunakan kemudian (tidak digunakan untuk training)
            # 3. Drop kolom non-numerik sesuai kode LSTM Anda
            drop_cols = ['timestamp', 'datapath_id', 'flow_id', 'ip_src', 'ip_dst', 'flags']
            flow_dataset = flow_dataset.drop(columns=drop_cols, errors='ignore')

            # 4. Handle missing values
            flow_dataset = flow_dataset.fillna(0)

            # 5. Label encode (jika ada kolom 'label')
            if 'label' not in flow_dataset.columns:
                self.logger.error("Kolom 'label' tidak ditemukan di FlowStatsfile.csv. Training dibatalkan.")
                return

            le = LabelEncoder()
            flow_dataset['label'] = le.fit_transform(flow_dataset['label'])

            # 6. Split fitur dan target
            X = flow_dataset.drop(columns=['label'])
            y = flow_dataset['label'].values

            # 7. Scaling
            scaler = MinMaxScaler()
            X_scaled = scaler.fit_transform(X.values.astype('float64'))

            # 8. Reshape ke 3D untuk LSTM (timesteps=1)
            X_lstm = X_scaled.reshape((X_scaled.shape[0], 1, X_scaled.shape[1]))

            # 9. Train-test split
            X_train, X_test, y_train, y_test = train_test_split(
                X_lstm, y, test_size=0.2, random_state=42
            )

            # 10. Build model (mirip dengan yang Anda berikan)
            n_features = X_train.shape[2]
            model = Sequential()
            model.add(LSTM(128, input_shape=(X_train.shape[1], X_train.shape[2]), return_sequences=False))
            model.add(Dropout(0.3))
            model.add(Dense(64, activation='relu'))
            model.add(Dropout(0.3))
            n_classes = len(np.unique(y_train))
            if n_classes <= 2:
                # binary classification -> gunakan 1 output dengan sigmoid (tapi karena Anda pakai sparse_categorical_crossentropy di kode awal, mempertahankan softmax)
                model.add(Dense(2, activation='softmax'))
                loss = 'sparse_categorical_crossentropy'
            else:
                model.add(Dense(n_classes, activation='softmax'))
                loss = 'sparse_categorical_crossentropy'

            model.compile(optimizer='adam', loss=loss, metrics=['accuracy'])

            # 11. Training (jumlah epoch/batch dapat disesuaikan)
            history = model.fit(
                X_train, y_train,
                epochs=30,
                batch_size=64,
                validation_data=(X_test, y_test),
                verbose=1
            )

            # 12. Evaluasi singkat
            loss_val, acc_val = model.evaluate(X_test, y_test, verbose=0)
            self.logger.info("Akurasi Test (LSTM): {:.2f}%".format(acc_val * 100))

            # 13. Simpan model & scaler & label encoder
            model.save("flow_model.h5")
            joblib.dump(scaler, "flow_scaler.save")
            joblib.dump(le, "flow_le.save")

            # 14. Assign ke atribut objek controller
            self.flow_model = model
            self.scaler = scaler
            self.le = le
            self.timesteps = 1
            self.features = n_features

            self.logger.info("Flow LSTM training selesai dan model disimpan sebagai flow_model.h5")
        except Exception:
            self.logger.exception("Error selama flow_training()")

    def flow_predict(self):
        """
        Baca PredictFlowStatsfile.csv, lakukan preprocessing yang identik, reshape,
        predict dengan LSTM, dan laporkan apakah traffic ddos atau legitimate.
        """
        try:
            if self.flow_model is None or self.scaler is None or self.le is None:
                self.logger.warning("Model atau scaler belum tersedia. Me-load jika file ada.")
                # coba load dari disk jika ada
                try:
                    if os.path.exists("flow_model.h5"):
                        self.flow_model = load_model("flow_model.h5")
                    if os.path.exists("flow_scaler.save"):
                        self.scaler = joblib.load("flow_scaler.save")
                    if os.path.exists("flow_le.save"):
                        self.le = joblib.load("flow_le.save")
                    self.timesteps = 1
                except Exception:
                    self.logger.exception("Gagal load model/scaler dari disk. Prediksi dilewatkan.")
                    return

            # baca file predict
            predict_flow_dataset = pd.read_csv('PredictFlowStatsfile.csv')

            if predict_flow_dataset.shape[0] == 0:
                # tidak ada data
                return

            # simpan ip_dst sebelum drop agar bisa menentukan victim
            ip_dst_series = None
            if 'ip_dst' in predict_flow_dataset.columns:
                ip_dst_series = predict_flow_dataset['ip_dst'].astype(str).values

            # lakukan preprocessing sama seperti training: drop kolom non-numerik
            drop_cols = ['timestamp', 'datapath_id', 'flow_id', 'ip_src', 'ip_dst', 'flags']
            df_proc = predict_flow_dataset.drop(columns=drop_cols, errors='ignore')
            df_proc = df_proc.fillna(0)

            # Pastikan kolom urutannya sama seperti saat training: kita asumsikan file FlowStatsfile.csv dan PredictFlowStatsfile.csv
            # memiliki kolom fitur identik setelah drop. Jika tidak identik, transformasi harus disesuaikan.
            X_predict = df_proc.values.astype('float64')

            # Jika scaler belum pernah fit, tidak bisa transform -> abort
            if self.scaler is None:
                self.logger.error("Scaler belum tersedia untuk transform. Prediksi dilewatkan.")
                return

            # transform dan reshape
            try:
                X_scaled = self.scaler.transform(X_predict)
            except Exception:
                # kemungkinan jumlah kolom berbeda -> log dan return
                self.logger.exception("Gagal melakukan scaler.transform — kemungkinan fitur tidak cocok.")
                return

            X_lstm = X_scaled.reshape((X_scaled.shape[0], 1, X_scaled.shape[1]))

            # predict
            preds_proba = self.flow_model.predict(X_lstm)
            preds = np.argmax(preds_proba, axis=1)

            legitimate_trafic = 0
            ddos_trafic = 0
            victim = None

            # hitung dan tentukan victim pertama jika ddos
            for idx, p in enumerate(preds):
                if p == 0:
                    legitimate_trafic += 1
                else:
                    ddos_trafic += 1
                    # coba ambil ip_dst dari ip_dst_series
                    if ip_dst_series is not None and idx < len(ip_dst_series):
                        ipdst = ip_dst_series[idx]
                        # ambil oktet terakhir ip sebagai host id, jika gagal default 0
                        try:
                            last_octet = int(str(ipdst).strip().split('.')[-1])
                            victim = last_octet % 20
                        except Exception:
                            victim = 0

            total = len(preds)
            self.logger.info("------------------------------------------------------------------------------")
            if total == 0:
                return

            if (legitimate_trafic / total * 100) > 80:
                self.logger.info("legitimate traffic ... ({}%)".format(round(legitimate_trafic / total * 100, 2)))
            else:
                self.logger.info("ddos traffic ... ({}% ddos)".format(round(ddos_trafic / total * 100, 2)))
                if victim is not None:
                    self.logger.info("victim is host: h{}".format(victim))
                else:
                    self.logger.info("victim unknown")

            self.logger.info("------------------------------------------------------------------------------")

            # kosongkan file predict untuk siklus berikutnya (tulis header saja)
            try:
                with open("PredictFlowStatsfile.csv", "w") as f:
                    f.write('timestamp,datapath_id,flow_id,ip_src,tp_src,ip_dst,tp_dst,ip_proto,icmp_code,icmp_type,flow_duration_sec,flow_duration_nsec,idle_timeout,hard_timeout,flags,packet_count,byte_count,packet_count_per_second,packet_count_per_nsecond,byte_count_per_second,byte_count_per_nsecond\n')
            except Exception:
                self.logger.exception("Gagal mengosongkan PredictFlowStatsfile.csv")
        except Exception:
            self.logger.exception("Error di flow_predict()")
