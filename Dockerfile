FROM python:3.8.1-alpine
ARG SERVICE_NAME
ARG SERVICE_VERSION
ENV SERVICE_NAME $SERVICE_NAME
ENV SERVICE_VERSION $SERVICE_VERSION
RUN mkdir /app
COPY . /app
RUN touch /app/.env
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --find-links /app/wheels -r /app/requirements.txt
RUN pip install pymysql gunicorn
RUN apk add --update --no-cache py3-numpy
ENV PYTHONPATH=/usr/lib/python3.8.1/site-packages
WORKDIR /app
EXPOSE 5000
CMD ["./boot.sh"]
