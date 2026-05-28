FROM 353605023268.dkr.ecr.us-east-1.amazonaws.com/python3_tox:latest

WORKDIR /pysoa/

COPY . .

CMD ["tox"]
