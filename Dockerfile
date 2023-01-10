FROM python:3.10

ARG VERSION

RUN apt-get update && apt-get install -y \
  git-crypt \
  && rm -rf /var/lib/apt/lists/*

RUN pip install git+https://github.com/jwoffindin/stk.git@$VERSION

ENV CONFIG_PATH=/config
ENV TEMPLATE_PATH=/templates

ENTRYPOINT ["stk"]
CMD ["-h"]
