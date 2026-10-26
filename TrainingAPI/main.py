import os

from sanic.response import text, json
# from sanic_redis import SanicRedis

from app import create_app
from app.apis import api
from app.misc.log import log
from config import Config, LocalDBConfig

app = create_app(Config, LocalDBConfig)

book_new = [{'id':1, 'title': 'a', 'price': 5},
            {'id':2, 'title': 'aa', 'price': 10},
            {'id':3, 'title': 'aaa', 'price': 15}]

@app.route("/", methods={'GET'})
async def hello_world(request):
    return text("Hello World")

@app.route('/hello', methods={'GET'})
async def xin_chao(request):
    return text('Xin chào, tôi đang học backend')

@app.route('/info', methods={'GET'})
async def get_info(request):
    a = {'name': 'T', 'course': "Backend training", 'module':1}
    return json(a)

@app.route('/greet', methods={'GET'})
async def gr(request):
    ten = request.args.get('name', '').strip()
    if ten == '':
        du_lieu = {"error": "Tên không được để trống"}
        return json(du_lieu, status=400, ensure_ascii = False)
    else:
        a = {'message':f'Xin chào {ten}'}
        return json(a, ensure_ascii = False)
    
@app.route('/demo/books/<book_id:int>', methods = {'GET'})
async def get_book(request, book_id):
    for book_id_new in book_new:
        if book_id_new["id"] == book_id:
            return json(book_id_new)
    else:
        a = {"error": "Không tìm thấy sách"}
        return json(a, status = 404, ensure_ascii= False)
    
@app.route('/demo/books', methods = {'GET'})
async def get_books(request):
    return json(book_new)

@app.route('/demo/echo', methods = {'POST'})
async def nhan_du_lieu(request):
    du_lieu = request.json
    return json(du_lieu, status = 200)

@app.route('/demo/books', methods = {'POST'})
async def add_book(request):
    du_lieu = request.json
    ten_sach = du_lieu.get('title', '').strip()
    gia_sach = du_lieu.get('price','')
    if ten_sach == '':
        er = {'error':"Tên sách không được để trống"}
        return json(er, status = 400)
    try:
        if gia_sach == '':
            err = {'error':"Gia sách không được để trống"}
            return json(err, status = 400)
        elif float(gia_sach) <= 0:
            err_1 = {'error':"Giá phải lớn hơn 0"}
            return json(err_1, status = 400)
    except ValueError:
        err_2 = {'error':"Giá phải là số"}
        return json(err_2, status = 400)
        
    for book in book_new:
        if du_lieu['id'] == book['id']:
            error = {"error": "ID sách đã tồn tại"}
            return json(error, status = 409)
    else:
        du_lieu['price'] = float(gia_sach)
        du_lieu["title"] = ten_sach.strip()
        book_new.append(du_lieu)
        return json(du_lieu, status = 201)

@app.route('/demo/books/<book_id:int>', methods = {'DELETE'})
async def del_book(request, book_id):
    for book in book_new:
        if book['id'] == book_id:
            book_new.remove(book)
            rp = {'message':"Đã xóa sách"}
            return json(rp, status = 200)
    else:
        er = {"error": "Không tìm thấy sách"}
        return json(er, status = 404)
    
@app.route('/demo/books/<book_id:int>', methods = {'PUT'})
async def put_book(request, book_id):
    for book in book_new:
        du_lieu = request.json
        ten_sach = du_lieu.get('title', '').strip()
        gia_sach = du_lieu.get('price','')
        if book['id'] == book_id:
            try:
                gia_sach = float(gia_sach)
            except ValueError:
                return json({"error": "Giá phải là số"}, status=400)
            if gia_sach <= 0:
                return json({"error": "Giá phải lớn hơn 0"}, status=400)
            if ten_sach == '':
                er = {'error':"Tên sách không được để trống"}
                return json(er, status = 400)
            book["title"] = ten_sach
            book["price"] = gia_sach
            return json(book, status = 200)
    else:
        er = {"error": "Không tìm thấy sách"}
        return json(er, status = 404)

if __name__ == '__main__':
    import argparse
    import ssl
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument('--https', action='store_true', help='Run local TLS on port 8443')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    settings = dict(app.config['RUN_SETTING'])
    if args.https:
        certificates = Path(__file__).resolve().parent / 'certs'
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(certificates / 'localhost.crt', certificates / 'localhost.key')
        settings.update(ssl=context, host='127.0.0.1', port=8443, workers=1, auto_reload=False, single_process=True)
    if args.port:
        settings['port'] = args.port
    if 'SECRET_KEY' not in os.environ:
        log(message='SECRET KEY is not set in the environment variable.', keyword='WARN')
    app.run(**settings)
