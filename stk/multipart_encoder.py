import codecs
import uuid
import io


_boundary = "//"

_content_types = {
    # Maps string prefix to mimetype
    "#!": "text/x-shellscript",
    "#cloud-boothook": "text/cloud-boothook",
    "#cloud-config": "text/cloud-config",
    "#cloud-config-archive": "text/cloud-config-archive",
    "#include": "text/x-include-url",
    "#include-once": "text/x-include-once-url",
    "#part-handler": "text/part-handler",
}


def multipart_encode(files: dict) -> str:
    """
    Given a dict of { filename => content }, returns byte array of UTF-8
    mime-encoded payload.
    """
    out = io.StringIO()

    out.write(f'Content-Type: multipart/mixed; boundary="{_boundary}"\n')
    out.write("MIME-Version: 1.0\n\n")

    for filename, content in files:
        content_type = guess_type(content.splitlines()[0])
        out.writelines(
            [
                "--" + _boundary + "\n",
                "MIME-Version: 1.0\n",
                "Content-Type: " + content_type + '; charset="utf-8"\n',
                'Content-Disposition: attachment; filename="' + filename + '"\n',
                "Content-Transfer-Encoding: utf-8\n",
                "\n",
                *content.splitlines(keepends=True),
                "\n\n",
            ]
        )
    out.write(f"--{_boundary}--\n")

    return out.getvalue()


def guess_type(first_line):
    for prefix, content_type in _content_types.items():
        if first_line.startswith(prefix):
            return content_type
    return "application/octet-stream"
