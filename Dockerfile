FROM python:3.10

RUN pip install git+https://github.com/jwoffindin/stk.git

ENV CONFIG_PATH=/config
ENV TEMPLATE_PATH=/templates

ENTRYPOINT ["stk"]
CMD ["-h"]
