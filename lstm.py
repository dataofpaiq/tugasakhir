# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, MinMaxScaler
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import LSTM, Dense, Dropout
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix

# === 1. Load Dataset ===
df = pd.read_csv("FlowStatsfile.csv")

print(df.head())
print("Dataset shape:", df.shape)

# === 2. Drop kolom non-numerik yang tidak relevan ===
drop_cols = ['timestamp', 'datapath_id', 'flow_id', 'ip_src', 'ip_dst', 'flags']
df = df.drop(columns=drop_cols, errors='ignore')

# Handle missing values
df = df.fillna(0)

# === 3. Encode label ===
le = LabelEncoder()
df['label'] = le.fit_transform(df['label'])

# === 4. Pisahkan fitur dan target ===
X = df.drop(columns=['label'])
y = df['label']

# Normalisasi fitur numerik
scaler = MinMaxScaler()
X_scaled = scaler.fit_transform(X)

# === 5. Reshape ke 3D untuk LSTM ===
# Bentuk: [samples, timesteps, features]
X_lstm = X_scaled.reshape((X_scaled.shape[0], 1, X_scaled.shape[1]))
print("Shape data untuk LSTM:", X_lstm.shape)

# === 6. Train-test split ===
X_train, X_test, y_train, y_test = train_test_split(
    X_lstm, y, test_size=0.2, random_state=42
)

# === 7. Bangun Model LSTM ===
model = Sequential()
model.add(LSTM(128, input_shape=(X_train.shape[1], X_train.shape[2]), return_sequences=False))
model.add(Dropout(0.3))
model.add(Dense(64, activation='relu'))
model.add(Dropout(0.3))
model.add(Dense(len(y.unique()), activation='softmax'))  # output multi-class

model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])

# === 8. Training ===
history = model.fit(
    X_train, y_train,
    epochs=50,
    batch_size=64,
    validation_data=(X_test, y_test),
    verbose=1
)

# === 9. Evaluasi ===
loss, acc = model.evaluate(X_test, y_test, verbose=0)
print(f"Akurasi Test: {acc*100:.2f}%")

# Prediksi
y_pred_encoded = model.predict(X_test)
y_pred = np.argmax(y_pred_encoded, axis=1)

# Classification Report
print(classification_report(y_test, y_pred))

# Confusion Matrix
cm = confusion_matrix(y_test, y_pred)
sns.heatmap(cm, annot=True, fmt='d', cmap="Blues")
plt.xlabel("Predicted")
plt.ylabel("True")
plt.show()

# Plot Akurasi
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

# === 10. Save Model ===
# Assign model ke atribut set.flow_model
set.flow_model = model
model.save("flow_model.h5")
print("Model berhasil disimpan sebagai flow_model.h5")

# === 11. Load model untuk prediksi ulang (opsional) ===
loaded_model = load_model("flow_model.h5")
sample_pred = loaded_model.predict(X_test[:5])  # contoh 5 data
print("Hasil prediksi sample:", np.argmax(sample_pred, axis=1))
print("Label asli:", y_test[:5].values)
