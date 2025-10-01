from datetime import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, MinMaxScaler
from sklearn.metrics import confusion_matrix, classification_report

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout

class MachineLearning():

    def __init__(self):
        print("Loading dataset ...")
        
        # Load dataset
        self.flow_dataset = pd.read_csv('FlowStatsfile.csv')

        # Bersihkan kolom IP/port yang non numerik jika ada (bisa disesuaikan dataset lu)
        drop_cols = ['timestamp', 'datapath_id', 'flow_id', 'ip_src', 'ip_dst', 'flags']
        self.flow_dataset = self.flow_dataset.drop(columns=drop_cols, errors='ignore')

        # Handle NaN
        self.flow_dataset = self.flow_dataset.fillna(0)

        # Encode label target
        le = LabelEncoder()
        self.flow_dataset['label'] = le.fit_transform(self.flow_dataset['label'])
        self.le = le  # simpan encoder buat nanti

    def flow_training(self):
        print("Flow Training with LSTM ...")

        # Pisahkan fitur dan target
        X = self.flow_dataset.drop(columns=['label'])
        y = self.flow_dataset['label']

        # Normalisasi
        scaler = MinMaxScaler()
        X_scaled = scaler.fit_transform(X)

        # Bentuk ulang untuk LSTM [samples, timesteps, features]
        X_lstm = X_scaled.reshape((X_scaled.shape[0], 1, X_scaled.shape[1]))

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X_lstm, y, test_size=0.2, random_state=42
        )

        # Bangun model LSTM
        model = Sequential()
        model.add(LSTM(128, input_shape=(X_train.shape[1], X_train.shape[2]), return_sequences=False))
        model.add(Dropout(0.3))
        model.add(Dense(64, activation='relu'))
        model.add(Dropout(0.3))
        model.add(Dense(len(np.unique(y)), activation='softmax'))  # multi-class output

        model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])

        # Training
        history = model.fit(
            X_train, y_train,
            epochs=30,
            batch_size=64,
            validation_data=(X_test, y_test),
            verbose=1
        )

        # Evaluasi
        loss, acc = model.evaluate(X_test, y_test, verbose=0)
        print(f"Akurasi Test: {acc*100:.2f}%")

        # Prediksi
        y_pred_encoded = model.predict(X_test)
        y_pred = np.argmax(y_pred_encoded, axis=1)

        # Classification report
        print(classification_report(y_test, y_pred, target_names=self.le.classes_))

        # Confusion matrix
        cm = confusion_matrix(y_test, y_pred)
        sns.heatmap(cm, annot=True, fmt='d', cmap="Blues")
        plt.xlabel("Predicted")
        plt.ylabel("True")
        plt.title("Confusion Matrix LSTM")
        plt.show()

        # Plot Accuracy
        plt.plot(history.history['accuracy'], label='Train Accuracy')
        plt.plot(history.history['val_accuracy'], label='Validation Accuracy')
        plt.title('Model Accuracy')
        plt.xlabel('Epoch')
        plt.ylabel('Accuracy')
        plt.legend()
        plt.show()

        # Plot Loss
        plt.plot(history.history['loss'], label='Train Loss')
        plt.plot(history.history['val_loss'], label='Validation Loss')
        plt.title('Model Loss')
        plt.xlabel('Epoch')
        plt.ylabel('Loss')
        plt.legend()
        plt.show()


def main():
    start = datetime.now()
    
    ml = MachineLearning()
    ml.flow_training()

    end = datetime.now()
    print("Training time: ", (end-start)) 

if __name__ == "__main__":
    main()
