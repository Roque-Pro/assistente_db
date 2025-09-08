from flask_cors import CORS
import pyodbc
from flask import Flask, request, jsonify, render_template, send_file
import requests
from io import BytesIO
from fpdf import FPDF
import base64
import matplotlib.pyplot as plt

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configurações da API Gemini
API_KEY = "AIzaSyDSaZy0BgAogkQyw3ISSGrPbxahccxIqwI"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# Conexão com banco de dados
def get_db_connection():
    try:
        conn = pyodbc.connect(
            'DRIVER={ODBC Driver 17 for SQL Server};'
            'SERVER=localhost;'
            'DATABASE=AdventureWorks2022;'
            'Trusted_Connection=yes;'
        )
        print("Conexão com o banco de dados bem-sucedida!")
        return conn
    except Exception as e:
        print(f"Erro ao conectar ao banco de dados: {str(e)}")
        return None

# Gera schema do banco de dados
def get_database_schema():
    conn = get_db_connection()
    if conn is None:
        return "Erro ao conectar para obter schema"

    cursor = conn.cursor()
    schema_description = ""
    try:
        cursor.execute("SELECT table_schema, table_name FROM information_schema.tables WHERE table_type = 'BASE TABLE'")
        tables = cursor.fetchall()

        for table in tables:
            schema_name = table[0]
            table_name = table[1]
            full_table_name = f"{schema_name}.{table_name}"

            cursor.execute(f"""
                SELECT COLUMN_NAME 
                FROM information_schema.columns 
                WHERE table_schema = ? AND table_name = ?
            """, (schema_name, table_name))
            columns = cursor.fetchall()
            column_names = [col[0] for col in columns]
            schema_description += f"Tabela {full_table_name}: colunas {', '.join(column_names)}\n"

        return schema_description
    except Exception as e:
        return f"Erro ao montar schema: {str(e)}"
    finally:
        conn.close()

# Consulta Gemini e retorna SQL
def get_gemini_response(question):
    schema = get_database_schema()
    headers = {"Content-Type": "application/json"}

    prompt = f"""
Você é um assistente SQL. Gere apenas a consulta SQL válida para Microsoft SQL Server com base na pergunta do usuário, usando apenas tabelas e colunas disponíveis.

Esquema do banco de dados:
{schema}

Pergunta do usuário:
{question}

IMPORTANTE:
- Não adicione comentários.
- Não use markdown.
- Retorne apenas a query SQL pura.
"""

    print("Prompt enviado ao Gemini:\n", prompt)

    response = requests.post(
        f"{GEMINI_API_URL}?key={API_KEY}",
        headers=headers,
        json={"contents": [{"parts": [{"text": prompt}]}]}
    )

    if response.status_code == 200:
        content = response.json()
        try:
            sql_query = content["candidates"][0]["content"]["parts"][0]["text"]
            sql_query = sql_query.strip().replace("```sql", "").replace("```", "").strip()
            print("Consulta gerada pela IA:", sql_query)
            return sql_query
        except (KeyError, IndexError):
            return "Erro na resposta da IA: formato inesperado."
    else:
        return f"Erro: {response.status_code}, {response.text}"

# Executa consulta SQL
def process_sql_query(sql_query):
    conn = get_db_connection()
    if conn is None:
        return "Erro ao conectar ao banco de dados"
    cursor = conn.cursor()
    try:
        print(f"Executando consulta: {sql_query}")
        cursor.execute(sql_query)
        columns = [column[0] for column in cursor.description]  # Pegando nomes das colunas
        results = cursor.fetchall()
        conn.close()

        results_list = [list(row) for row in results]

        # Retornar com cabeçalho para frontend mostrar colunas reais
        return {"columns": columns, "rows": results_list}
    except Exception as e:
        conn.close()
        return f"Erro ao executar consulta: {str(e)}"

# Gera dados de gráfico
def generate_graphs(data):
    # Espera-se que data seja dict com 'columns' e 'rows'
    if not data or not isinstance(data, dict):
        return []

    rows = data.get('rows')
    columns = data.get('columns')
    if not rows or len(columns) < 2:
        return []

    labels = [str(row[0]) for row in rows]
    try:
        values = [float(row[1]) for row in rows]
    except Exception:
        # Se não conseguir converter, retorna vazio
        return []

    graph = {
        "labels": labels,
        "datasets": [{
            "label": "Valores",
            "data": values,
            "borderColor": "rgba(75, 192, 192, 1)",
            "backgroundColor": "rgba(75, 192, 192, 0.2)",
            "fill": False,
            "tension": 0.1
        }]
    }

    # Gera imagem base64 para PDF
    try:
        plt.figure(figsize=(6, 4))
        plt.plot(labels, values, marker='o')
        plt.title("Gráfico Gerado")
        plt.xlabel(columns[0])
        plt.ylabel(columns[1])
        plt.xticks(rotation=45)
        plt.tight_layout()

        img_bytes = BytesIO()
        plt.savefig(img_bytes, format='png')
        img_bytes.seek(0)
        img_base64 = base64.b64encode(img_bytes.read()).decode('utf-8')
        plt.close()

        graph["img_b64"] = img_base64
    except Exception as e:
        print("Erro ao gerar imagem base64:", e)

    return [graph]

# Gera o PDF com gráficos
def generate_pdf(text, graphs):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, text)

    for graph in graphs:
        img_data = graph.get('img_b64')
        if img_data:
            img_bytes = BytesIO(base64.b64decode(img_data))
            pdf.ln(10)
            # Define largura da imagem e mantém proporção
            effective_page_width = pdf.w - 2 * pdf.l_margin
            pdf.image(img_bytes, x=10, y=pdf.get_y(), w=effective_page_width * 0.9)


    output = BytesIO()
    pdf.output(output)
    output.seek(0)
    return output

# GET /get_tables
@app.route('/get_tables', methods=['GET'])
def get_tables():
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Falha ao conectar ao banco de dados"}), 500

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT table_schema, table_name FROM information_schema.tables WHERE table_type = 'BASE TABLE'")
        tables = cursor.fetchall()

        table_columns = {}
        for table in tables:
            schema_name = table[0]
            table_name = table[1]
            full_table_name = f"{schema_name}.{table_name}"

            cursor.execute("""
                SELECT COLUMN_NAME 
                FROM information_schema.columns 
                WHERE table_schema = ? AND table_name = ?
            """, (schema_name, table_name))
            cols = cursor.fetchall()
            table_columns[full_table_name] = [col[0] for col in cols]

        conn.close()
        return jsonify(table_columns)
    except Exception as e:
        conn.close()
        return jsonify({"error": f"Erro ao obter as tabelas: {str(e)}"}), 500

# POST /ask
@app.route('/ask', methods=['POST'])
def ask():
    data = request.get_json()
    question = data.get('question')
    if not question:
        return jsonify({'error': 'Pergunta não fornecida'}), 400

    ai_sql_query = get_gemini_response(question)
    results = process_sql_query(ai_sql_query)

    graphs = []
    response_text = f"<p><strong>Resposta para sua pergunta:</strong> {question}</p>"

    if isinstance(results, dict) and "rows" in results and "columns" in results:
        rows = results["rows"]
        columns = results["columns"]

        if rows and len(columns) == 2:
            # Gera a tabela HTML formatada
            response_text += """
                <table class='report-table'>
                    <thead>
                        <tr><th>{}</th><th>{}</th></tr>
                    </thead>
                    <tbody>
            """.format(columns[0], columns[1])

            for row in rows:
                response_text += f"<tr><td>{row[0]}</td><td>{row[1]}</td></tr>"

            response_text += "</tbody></table>"
        else:
            response_text += "<pre>" + str(rows) + "</pre>"

        graphs = generate_graphs(results)
    else:
        response_text += f"<p style='color:red;'>Erro ao executar a consulta: {results}</p>"

    return jsonify({
        'response_text': response_text,
        'graphs': graphs,
        'sql_query': ai_sql_query,
        'query_result': results
    })

# POST /download_pdf
@app.route('/download_pdf', methods=['POST'])
def download_pdf():
    data = request.get_json()
    text = data.get('text')
    graphs = data.get('graphs')
    pdf = generate_pdf(text, graphs)
    return send_file(
        pdf,
        mimetype='application/pdf',
        download_name='relatorio.pdf',
        as_attachment=True
    )

# GET /
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
