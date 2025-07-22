# Importar las herramientas necesarias
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import csv
from io import StringIO
import json
import re

app = Flask(__name__)
CORS(app, resources={r"/webhook/*": {"origins": "*"}})

# --- CONFIGURACIÓN ---
# PEGA TU ENLACE CSV DE "PUBLICAR EN LA WEB" AQUÍ DENTRO DE LAS COMILLAS
URL_GOOGLE_SHEET_CSV = "PEGA_TU_ENLACE_CSV_AQUI"

# --- LÓGICA DE EXTRACCIÓN DE DATOS ---
def extraer_datos_pedido(mensaje):
    datos = {"cantidad": None, "ancho": None, "alto": None, "terminos_busqueda": []}
    mensaje_lower = mensaje.lower()

    medidas_match = re.search(r'(\d+\.?\d*)\s*x\s*(\d+\.?\d*)', mensaje_lower)
    if medidas_match:
        datos["ancho"] = float(medidas_match.group(1))
        datos["alto"] = float(medidas_match.group(2))

    todos_los_numeros = re.findall(r'\d+\.?\d*', mensaje_lower)
    numeros_de_medidas_str = [medidas_match.group(1), medidas_match.group(2)] if medidas_match else []

    for num_str in todos_los_numeros:
        if num_str not in numeros_de_medidas_str:
            datos["cantidad"] = int(float(num_str))
            break

    palabras = re.sub(r'[\d.x,]', '', mensaje_lower).split()
    datos["terminos_busqueda"] = [p for p in palabras if len(p) > 2]
    return datos

# --- CÓDIGO DEL SERVIDOR ---
def buscar_producto(terminos_busqueda):
    try:
        respuesta = requests.get(URL_GOOGLE_SHEET_CSV)
        respuesta.raise_for_status()
        datos_csv = StringIO(respuesta.text)
        lector = csv.DictReader(datos_csv)
        for fila in lector:
            nombre_producto = fila.get('Nombre_Producto', '').lower()
            if not terminos_busqueda: continue
            if all(term.lower() in nombre_producto for term in terminos_busqueda):
                return fila
        return None
    except Exception as e:
        print(f"Error buscando producto: {e}")
        return None

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    datos_cliente = request.get_json()
    if not datos_cliente or 'text' not in datos_cliente:
        return jsonify({"error": "Petición inválida."}), 400

    mensaje_cliente = datos_cliente.get('text', '')
    datos_extraidos = extraer_datos_pedido(mensaje_cliente)

    cantidad = datos_extraidos["cantidad"]
    ancho = datos_extraidos["ancho"]
    alto = datos_extraidos["alto"]
    terminos_busqueda = datos_extraidos["terminos_busqueda"]

    producto = buscar_producto(terminos_busqueda)

    if not producto:
        return jsonify({"respuesta": "Lo siento, no pude identificar el producto en tu pedido. Por favor, sé más específico."})

    if not all([cantidad, ancho, alto]):
        return jsonify({"respuesta": f"Para cotizar '{producto['Nombre_Producto']}', por favor indica la cantidad y las medidas (ej: 100 unidades de 4x5 pulgadas)."})

    v_valor = float(producto.get('V_Valor', 0))
    m_minimo = float(producto.get('M_Minimo', 0))

    precio_base = (cantidad * ancho * alto / 144) * v_valor
    precio_final = max(m_minimo, precio_base)

    respuesta_formateada = f"{producto['Nombre_Producto']}\n{cantidad} unidades de {ancho}x{alto} pulgadas\nPrecio: ${precio_final:,.2f}"

    return jsonify({"respuesta": respuesta_formateada})

@app.route('/')
def home():
    return "Servidor de cálculo activo."

if __name__ == "__main__":
    app.run()
