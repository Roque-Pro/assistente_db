import openai  # Para interagir com a API do Gemini
import matplotlib.pyplot as plt
from io import BytesIO

openai.api_key = "sua-chave-gemini"

def get_gemini_response(question):
    # Envia a pergunta para a Gemini API
    response = openai.Completion.create(
        engine="gemini-1",  # Verifique o nome correto do modelo
        prompt=question,
        max_tokens=100
    )
    
    text_response = response['choices'][0]['text']
    graphs = generate_graphs_based_on_question(question)

    return text_response, graphs

def generate_graphs_based_on_question(question):
    # Dependendo da pergunta, você pode gerar gráficos dinâmicos com o Matplotlib/Chart.js
    # Exemplo de gráfico fictício
    x = [1, 2, 3, 4]
    y = [10, 20, 25, 40]
    
    plt.figure(figsize=(5,3))
    plt.plot(x, y)
    plt.title("Exemplo de Gráfico")

    # Salvar a imagem em um buffer para enviar ao frontend
    img = BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    
    # Retorna a imagem codificada como base64
    import base64
    img_b64 = base64.b64encode(img.read()).decode('utf-8')
    return [{"type": "line", "img_b64": img_b64}]

def generate_pdf(report):
    # Utiliza uma biblioteca como WeasyPrint ou ReportLab para gerar o PDF
    from weasyprint import HTML
    
    html_content = f"<h1>Relatório IA</h1><p>{report}</p>"
    pdf = HTML(string=html_content).write_pdf()
    
    return pdf
