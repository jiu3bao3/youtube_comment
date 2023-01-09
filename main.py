# -*- coding: utf-8 -*-
# Youtubeコメントダウンローダー
# Author: 久保　由仁
# Date: 2023.01.07
from flask import Flask, Response, make_response
import functions_framework
import json
import os
import requests
import tempfile

RECORD_FORMAT = '"{}","{}","{}"\n'

class APIException(Exception):
  """
  API呼出のエラー
  """
  def __init__(self, code, text):
    self.code = code
    self.text = text
    super().__init__("APIの呼出でエラーが発生しました。status:{code}, message{text}".format(code=code, text=text))

@functions_framework.http
def get_comments(request):
  """HTTP Cloud Function.
  Args:
    request (flask.Request): The request object.
    <https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data>
  Returns:
    The response text, or any set of values that can be turned into a
    Response object using `make_response`
    <https://flask.palletsprojects.com/en/1.1.x/api/#flask.make_response>.
   """
  if request.method == 'GET':
    response = do_get(request)
  else:
    response = do_post(request)
  return response

def do_get(request):
  """
  GETリクエストを処理する

  Args:
    request : Request
  Returns:
    Response 
  """
  if len(request.query_string.decode('utf-8')) == 0:
    return handle_init_access()
  else:
    return handle_login(request)

def do_post(request):
  """
  POSTリクエストを処理する

  Args:
    request : Request
  Returns:
    Response 
  """
  if 'channel_id' in request.form:
    response = make_response()
    try:
      response.data = execute_job(request)
      response.headers['Content-Type'] = 'application/octet-stream'
      response.headers['Content-Disposition'] = "attachment; filename=comment_{}.csv".format(request.form['channel_id'])
    except Exception as e:
      with open("./form.html", 'r') as f:
        template = f.read()
        response.data = template.format(access_token=request.form['access_token'], message=str(e))
      response.headers['Content-Type'] = 'text/html'
    finally:
      return response
  else:
    return handle_token(request)

def handle_init_access():
  """
  初期画面用のhtmlを返す

  Returns:
    String
      初期画面用のhtml
  """
  template = ''
  with open("./init.html", 'r') as f:
    template = f.read()
  return template.format(client_id=os.environ.get('CLIENT_ID'), limit=os.environ.get('LIMIT'), redirect_uri=os.environ.get('REDIRECT_URI'))

def handle_login(request):
  """
  認証処理を行う

  Args:
    request : Request
  Returns:
    認証用html
  """
  template = ''
  with open("./login.html", 'r') as f:
    template = f.read()
  client_id = os.environ.get('CLIENT_ID')
  client_secret = os.environ.get('CLIENT_SECRET')
  redirect_uri = os.environ.get('REDIRECT_URI')
  return template.format(client_id=client_id, client_secret=client_secret, code=request.args['code'], redirect_uri=redirect_uri)

def get_tokens(request):
  """
  アクセストークンを取得する

  Args:
    request : Request
  Returns:
    Dictionary
      succes: 成功か否か，status_code : API応答のHTTPステータスコード，access_token : アクセストークン，refresh_token : リフレッシュトークン，message : メッセージ
  """
  params = { "code" : request.form['code'], "grant_type" : "authorization_code", "client_secret" : os.environ.get('CLIENT_SECRET'), \
             "client_id" : os.environ.get('CLIENT_ID'), "redirect_uri" : os.environ.get('REDIRECT_URI') }
  header = { "Content-Type" : "application/json" }
  response = requests.post("https://oauth2.googleapis.com/token", params=params, headers=header)
  if response.status_code == 200:
    result = json.loads(response.text)
    tokens = { "success" : True, "status_code" : 200, "access_token" : result['access_token'], "refresh_token" : result['refresh_token'], "message" : "" }
  else:
    tokens = { "success" : False, "status_code" : response.status_code, "access_token" : None, "refresh_token" : None, "message" : response.text }
  return tokens

def handle_token(request):
  """
  トークンエンドポイントからのレスポンスからアクセストークンを読込み，処理実行画面のhtmlを返す

  Args:
    request : Request
  Returns:
    String
      処理実行画面のhtml
  """
  tokens = get_tokens(request)
  with open("./form.html", 'r') as f:
    template = f.read()
    return template.format(access_token=tokens['access_token'], message=tokens['message'], redirect_uri=os.environ.get('REDIRECT_URI'))

def execute_job(request):
  """
  Youtubeのコメント取得処理を実行する

  Args:
    request : Request
  Returns:
    String
      取得したコメントをCSVにした文字列
  """
  access_token = request.form['access_token']
  channel_id = request.form['channel_id']
  #if not channel_id in ALLOWED_CANNELS:
  #  raise Exception("許可されていないチャンネルIDです。{}".format(channel_id))
  limit = int(os.environ.get('LIMIT'))
  total_count = 0
  with tempfile.TemporaryFile(mode='r+', encoding='utf-8') as fp:
    token = None
    while True:
      next_token = list_comments(fp, token, channel_id, access_token)
      total_count += next_token['count']
      token = next_token['token'] if total_count <= limit else None
      if token == None:
        fp.seek(0)
        return fp.read()

def list_comments(f, token, channel_id, access_token):
  """
  Youtubeコメントを取得して一時ファイルに保存し，次のトークンと件数を含むDictionaryを返す

  Args:
    f : Tempfile
      取得結果を書き込む一時ファイル
    token : String
      次のページを示すトークン
    channel_id : String
      YoutubeのチャンネルID
    access_token : String
      Youtube APIのアクセストークン
  Returns:
    Dictionary
      token : 次のページを示すトークン，count : 件数
  """
  url = "https://www.googleapis.com/youtube/v3/commentThreads"
  header = { "authorization" : "Bearer {}".format(access_token) }
  param = { "part" : "snippet", "allThreadsRelatedToChannelId" :  channel_id, "textFormat" : "plainText" }
  if not token == None:
    param['pageToken'] = token
  response = requests.get(url, params = param, headers = header)
  count = 0
  if response.status_code == 200:
    result = json.loads(response.text)
    next_page_token = result['nextPageToken'] if 'nextPageToken' in result else None
    for item in result['items']:
      snippet = item['snippet']['topLevelComment']['snippet']
      text = snippet["textOriginal"].replace("\r", "").replace("\n", "\\n")
      f.write(RECORD_FORMAT.format(snippet['publishedAt'], snippet["authorDisplayName"], text))
      count += 1
    f.flush()
    return { 'token' : next_page_token, 'count' : count }
  else:
    raise APIException(response.status_code, response.text)
