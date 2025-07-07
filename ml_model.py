from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
import numpy as np

def entrenar_modelo(df):
    df['Target'] = np.where(df['Close'].shift(-1) > df['Close'], 1, 0)
    df.dropna(inplace=True)
    features = ['RSI', 'MACD', 'MA20', 'MA50', 'ATR']
    X = df[features]
    y = df['Target']
    X_train, X_test, y_train, y_test = train_test_split(X, y, shuffle=False, test_size=0.2)
    model = XGBClassifier(use_label_encoder=False, eval_metric='logloss')
    model.fit(X_train, y_train)
    accuracy = model.score(X_test, y_test)
    return model, accuracy

def predecir_direccion(modelo, datos_actuales):
    proba = modelo.predict_proba(datos_actuales)[0]
    etiqueta = modelo.predict(datos_actuales)[0]
    confianza = np.max(proba)
    direccion = 'subir' if etiqueta == 1 else 'bajar'
    return direccion, confianza