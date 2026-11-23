#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把本地文件按 ima create_media 返回的 cos_credential 上传到 COS。
用法：
  python ima_cos_upload.py --file <本地文件> --cred <create_media返回的json>

cred json 结构（直接保存 create_media 的返回体即可）：
  { "media_id": "...", "cos_credential": { "token","secret_id","secret_key",
    "bucket_name","region","cos_key","start_time","expired_time" }, "upload_mode": 0 }

退出码 0 = 上传成功；非 0 = 失败（stderr 给出原因）。
"""
import argparse
import hashlib
import hmac
import json
import os
import sys
import urllib.parse

import requests

CONTENT_TYPES = {
    "md": "text/markdown",
    "markdown": "text/markdown",
    "txt": "text/plain",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "csv": "text/csv",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}


def hmac_sha1_hex(key, msg):
    return hmac.new(key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha1).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--cred", required=True)
    args = ap.parse_args()

    if not os.path.exists(args.file):
        print("ERROR: 文件不存在 %s" % args.file, file=sys.stderr)
        return 2

    raw = json.load(open(args.cred, encoding="utf-8"))
    if isinstance(raw, list):
        raw = raw[0]
    if "results" in raw:
        raw = raw["results"][0]
    cred = raw.get("cos_credential") or {}
    media_id = raw.get("media_id", "")

    need = ["token", "secret_id", "secret_key", "bucket_name", "region", "cos_key"]
    missing = [k for k in need if not cred.get(k)]
    if missing:
        print("ERROR: cos_credential 缺字段 %s" % ",".join(missing), file=sys.stderr)
        return 3

    ext = os.path.splitext(args.file)[1].lower().lstrip(".")
    content_type = CONTENT_TYPES.get(ext)
    if not content_type:
        print("ERROR: 不支持的扩展名 .%s" % ext, file=sys.stderr)
        return 4

    data = open(args.file, "rb").read()
    bucket = cred["bucket_name"]
    region = cred["region"]
    cos_key = cred["cos_key"]
    token = cred["token"]
    secret_id = cred["secret_id"]
    secret_key = cred["secret_key"]
    start = str(cred.get("start_time") or "")
    expired = str(cred.get("expired_time") or "")
    if not start or not expired:
        print("ERROR: cos_credential 缺 start_time/expired_time", file=sys.stderr)
        return 5

    host = "%s.cos.%s.myqcloud.com" % (bucket, region)
    pathname = "/" + cos_key

    sign_time = "%s;%s" % (start, expired)
    sign_key = hmac_sha1_hex(secret_key, sign_time)

    headers_to_sign = {
        "content-type": content_type,
        "host": host,
        "x-cos-security-token": token,
    }
    header_list = ";".join(sorted(headers_to_sign))
    http_headers = "&".join(
        "%s=%s" % (urllib.parse.quote(k, safe=""), urllib.parse.quote(v, safe=""))
        for k, v in sorted(headers_to_sign.items())
    )
    http_string = "put\n%s\n\n%s\n" % (pathname, http_headers)
    string_to_sign = "sha1\n%s\n%s\n" % (sign_time, hashlib.sha1(http_string.encode("utf-8")).hexdigest())
    signature = hmac_sha1_hex(sign_key, string_to_sign)

    authorization = (
        "q-sign-algorithm=sha1&q-ak=%s&q-sign-time=%s&q-key-time=%s"
        "&q-header-list=%s&q-url-param-list=&q-signature=%s"
        % (secret_id, sign_time, sign_time, header_list, signature)
    )

    url = "https://%s%s" % (host, pathname)
    resp = requests.put(
        url,
        data=data,
        headers={
            "Authorization": authorization,
            "Content-Type": content_type,
            "x-cos-security-token": token,
            "Content-Length": str(len(data)),
        },
        timeout=90,
    )

    if resp.status_code != 200:
        print("ERROR: HTTP %s %s" % (resp.status_code, resp.text[:300]), file=sys.stderr)
        return 6

    print("OK media_id=%s bytes=%d" % (media_id, len(data)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
