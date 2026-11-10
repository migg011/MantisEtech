# Imagem somente da API: instala dependências fixadas e publica a aplicação WSGI com Waitress.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY . .
RUN useradd --create-home mantis && chown -R mantis:mantis /app
# A aplicação roda com usuário sem privilégios de root dentro do contêiner.
USER mantis
EXPOSE 8000
CMD ["waitress-serve", "--listen=0.0.0.0:8000", "config.wsgi:application"]
