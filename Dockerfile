FROM python:3.12-alpine

WORKDIR /app

# Install app dependencies
COPY src/requirements.txt ./

RUN pip install -r requirements.txt

# Bundle app source
COPY src /app

ARG VERSION=12.99

RUN cd /tmp && \
    apk --update add perl && \
    wget https://exiftool.org/Image-ExifTool-$VERSION.tar.gz && \
    tar -xzvf Image-ExifTool-*.tar.gz && \
    rm -rf Image-ExifTool-*.tar.gz && \
    cd Image-ExifTool-* && \
    rm -rf html t Change Makefile.PL MANIFEST META.json META.yml perl-Image-ExifTool.spec README && \
    mv * /usr/local/bin/ && \
    rm -rf /tmp/Image-ExifTool-*

CMD ["python", "motionphoto2.py", "--input-directory", "/input", "--output-directory", "/output"]
