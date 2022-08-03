FROM python:3.10

ARG VERSION

RUN pip install git+https://github.com/jwoffindin/stk.git@$VERSION

ENV CONFIG_PATH=/config
ENV TEMPLATE_PATH=/templates

ENTRYPOINT ["stk"]
CMD ["-h"]
