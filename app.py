import random
import string
import logging
from flask import Flask, request, jsonify, redirect, render_template
import psycopg2
import redis

# Configuração do banco de dados PostgreSQL
db_conn = psycopg2.connect(
    host='db',
    port='5432',
    database='url_shortener',
    user='admin',
    password='admin'
)
db_cursor = db_conn.cursor()

# Configuração do Redis para cache
redis_conn = redis.Redis(host='localhost', port=6379, db=0)

# Configuração do logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

handler = logging.FileHandler('app.log')
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Criação do aplicativo Flask
app = Flask(__name__)
app.logger.addHandler(logging.StreamHandler())  # Adicione esta linha para registrar mensagens de log na saída padrão

@app.route('/')
def index():
    app.logger.info('Acessou a página inicial')
    return render_template('index.html')

@app.route('/encurtar', methods=['POST'])
def encurtar_url():
    url = request.form['url']
    app.logger.debug(f'Recebida uma solicitação para encurtar a URL: {url}')

    # Verificar se a URL já existe no banco de dados
    db_cursor.execute("SELECT codigo FROM urls WHERE url = %s", (url,))
    existing_short_url = db_cursor.fetchone()

    if existing_short_url:
        short_url = existing_short_url[0]
    else:
        short_url = gerar_codigo()
        cache_key = f'url:{short_url}'
        redis_conn.set(cache_key, url)
        redis_conn.expire(cache_key, 3600)  # Definir expiração para 1 hora (3600 segundos)
        db_cursor.execute("INSERT INTO urls (codigo, url) VALUES (%s, %s)", (short_url, url))
        db_conn.commit()

    full_url = request.host_url + short_url  # Obter a URL completa com base no host atual
    app.logger.info(f'URL encurtada gerada: {full_url}')
    return full_url, 201


@app.route('/<short_url>', methods=['GET'])
def redirecionar_url(short_url):
    app.logger.debug(f'Recebida uma solicitação para redirecionar a URL com código: {short_url}')

    cache_key = f'url:{short_url}'
    url = redis_conn.get(cache_key)

    if url is None:
        db_cursor.execute("SELECT url FROM urls WHERE codigo = %s", (short_url,))
        url = db_cursor.fetchone()

        if url is None:
            app.logger.warning(f'URL não encontrada para o código: {short_url}')
            return jsonify({'error': 'URL não encontrada'}), 404
        else:
            url = url[0]
            redis_conn.set(cache_key, url)
            redis_conn.expire(cache_key, 3600)  # Definir expiração para 1 hora (3600 segundos)
    else:
        url = url.decode('utf-8')

    app.logger.info(f'Redirecionando para a URL: {url}')
    return redirect(url)

def gerar_codigo(tamanho=6):
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for _ in range(tamanho))

if __name__ == '__main__':
    app.run()
