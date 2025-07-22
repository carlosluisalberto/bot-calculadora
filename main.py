# Importar las herramientas necesarias
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
import csv
from io import StringIO
import json
import re # Importamos la librería de expresiones regulares para buscar números

# Crear el servidor web
app = Flask(__name__)
CORS(app, resources={r"/webhook/*": {"origins": "*"}})

# --- CONFIGURACIÓN ---
# ¡ASEGÚRATE DE QUE ESTA SEA TU URL CORRECTA DE GOOGLE SHEETS!
URL_GOOGLE_SHEET_CSV = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRDiJdEibznvruFGgZ--qa6LMr3bvgUZLDuo4Ov4KusFStdSo8K0sxk03gsiRwNUGwfoPa39bL3MI-u/pub?output=csv"

# --- LÓGICA DE EXTRACCIÓN DE DATOS (NUEVA SECCIÓN) ---
def extraer_datos_pedido(mensaje):
    """
    Analiza el mensaje del cliente para extraer cantidad, ancho y alto.
    Devuelve un diccionario con los datos encontrados.
    """
    datos = {
        "cantidad": None,
        "ancho": None,
        "alto": None,
        "terminos_busqueda": []
    }

    # 1. Extraer medidas (ej: 4x5, 2.5x3, etc.)
    medidas_match = re.search(r'(\d+\.?\d*)\s*x\s*(\d+\.?\d*)', mensaje, re.IGNORECASE)
    if medidas_match:
        datos["ancho"] = float(medidas_match.group(1))
        datos["alto"] = float(medidas_match.group(2))

    # 2. Extraer cantidad (ej: 100 stikers, 50 und, etc.)
    # Busca un número que no sea parte de las medidas que ya encontramos.
    todos_los_numeros = re.findall(r'\d+\.?\d*', mensaje)
    numeros_de_medidas = [medidas_match.group(1), medidas_match.group(2)] if medidas_match else []
    
    for num_str in todos_los_numeros:
        if num_str not in numeros_de_medidas:
            datos["cantidad"] = int(float(num_str))
            break # Nos quedamos con el primer número que no sea una medida

    # 3. Extraer términos de búsqueda (palabras clave del producto)
    palabras = re.sub(r'[\d.x,]', '', mensaje).split() # Quita números y símbolos
    datos["terminos_busqueda"] = [p for p in palabras if len(p) > 2]

    return datos

# --- El resto del código permanece similar ---

def buscar_producto(terminos_busqueda):
    try:
        respuesta = requests.get(URL_GOOGLE_SHEET_CSV)
        respuesta.raise_for_status()
        datos_csv = StringIO(respuesta.text)
        lector = csv.DictReader(datos_csv)
        for fila in lector:
            nombre_producto = fila.get('Nombre_Producto', '').lower()
            if all(term.lower() in nombre_producto for term in terminos_busqueda):
                return fila
        return None
    except Exception as e:
        print(f"Error buscando producto: {e}")
        return None

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    if request.is_json:
        datos_cliente = request.get_json()
    else:
        # Esto es para el formulario de prueba, lo mantenemos por ahora
        json_string_from_form = request.form.get('data')
        try:
            datos_cliente = json.loads(json_string_from_form)
        except:
            return jsonify({"error": "Formato JSON inválido."}), 400

    mensaje_cliente = datos_cliente.get('text', '')

    # --- LÓGICA PRINCIPAL ACTUALIZADA ---
    # 1. Usar la nueva función para analizar el mensaje
    datos_extraidos = extraer_datos_pedido(mensaje_cliente)
    
    cantidad = datos_extraidos["cantidad"]
    ancho = datos_extraidos["ancho"]
    alto = datos_extraidos["alto"]
    terminos_busqueda = datos_extraidos["terminos_busqueda"]

    # 2. Buscar el producto
    producto = buscar_producto(terminos_busqueda)

    if not producto:
        return jsonify({"respuesta": "Lo siento, no pude identificar el producto en tu pedido."})

    # 3. Validar que tenemos todos los datos para calcular
    if not all([cantidad, ancho, alto]):
        # Aquí podrías añadir lógica para preguntar al cliente por los datos que faltan
        return jsonify({"respuesta": f"Para cotizar {producto['Nombre_Producto']}, necesito la cantidad y las medidas (ej: 100 unidades de 4x5 pulgadas)."})

    # 4. Calcular el precio
    v_valor = float(producto.get('V_Valor', 0))
    m_minimo = float(producto.get('M_Minimo', 0))
    
    precio_base = (cantidad * ancho * alto / 144) * v_valor
    precio_final = max(m_minimo, precio_base)
    
    respuesta_formateada = f"{producto['Nombre_Producto']}\n{cantidad} unidades de {ancho}x{alto} pulgadas\nPrecio: ${precio_final:,.2f}"
    
    return jsonify({"respuesta": respuesta_formateada})

# Ruta para el formulario de prueba
@app.route('/')
def index():
    return "El servidor de cálculo está funcionando. Listo para recibir peticiones del bot."

# Iniciar el servidor
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=81)
