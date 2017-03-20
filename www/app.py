import logging
#设置logging的默认level为INFO，日志级别：critical > error > warning > info > debug > notset
logging.basicConfig(level=logging.INFO)
import asyncio
import os
import json
import time
from datetime import datetime
from aiohttp import web
#jinja2是仿照Django模板的Python前端引擎模板
#ervironment指的是jinja2模板的配置文件，filesystemloader是文件系统加载器，用来加载模板路径
from jinja2 import Environment,FileSystemLoader
import orm
from coroweb import add_routes,add_static
from handlers import cookie2user,COOKIE_NAME
#这个函数的功能是初始化的jinja2模板，配置jinja2的环境
def init_jinja2(app,**kw):
    logging.info('init jinja2...')
    #设置解析模板需要用到的环境变量
    options = dict(
        autoescape = kw.get('autoespace',True), #自动转义xml、html的特殊字符
        #下面是{%和%}中间的是Python代码而不是html
        block_start_string =kw.get('block_start_string','{%'),
        block_end_string = kw.get('block_end_string','%}'),
        variable_start_string = kw.get('variable_start_string','{{'),
        variable_end_string = kw.get('variable_end_string','}}'),
        auto_reload = kw.get('auto_reload',True)
    )
    path = kw.get('path',None)
    if path is None:
        #os.path.abspath(__file__)
        #os.path.dirname()
        #os.path.join(path,name)
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'templates')
    logging.info('set jinja2 template path:%s' % path)
    #loader=FileSystemLoadr(path)指到哪个目录下加载模板文件，**options就是前面的options
    env = Enviroment(loader=FilesSystemLoader(path),**pations)
    filters = kw.get('filters',None)   #fillters=>过滤器
    if filters is not None:
        for name,f in filters.items():
            env.filters[name] = f
    app['__templating__'] = env  #把env存入app的dict中，这样app就知道去哪找模板，解析模板
    #当http请求时，通过logging.info输出请求信息，其中包括请求的方法和路径
async def logger_factory(app,handler):
    async def logger(request):
        logging.info('request:%s %s' % (request.method,request.path))
        #await asyncio.sleep(0.3)
        return (await handler(request))
    return logger
#,iddlewares的作用是在处理请求之前，现将cookie解析出来，并将登录用户绑定到request对象上
#以后的每个请求，都在middle之后处理，都已绑定了用户信息
@asyncio.coroutine
def auth_factory(app,handler):
    @asyncio.coroutione
    def auth(request):
        logging.info('check user: %s %s' % (request.method,rquest.path))
        request.__user__ = None #先把请求的__user__属性绑定None
        cookie_str = request.cookie.get(COOKIE_NAEM)
        if cookie_str:
            user = yield from cookie2user(cookie_str)   #验证cookie，并得到用户信息
            if user:
                logging.info('set current user: %s ' % user.email)
                request.__user__ = user #将用户信息绑定到请求上
            #如果请求页面是管理页面，但是用户不是管理员，奖从定向到登录页面
        if request.path.startswit('/manage/') and (request.__user__ is None or not request.__user__.admin):
           return web.HTTPFound('/signin')
        return (yield from handler(request))
    return auth
#只有请求方法为post时这个函数才起作用
async def data_factory(app,handler):
    async def parse_data(request):
        if request.methd == 'POST':
            if request.content_type.startswith('application/json'):
                request.__data__ = await request.json()
                logging.info('request json: %s' % str(request.__data__))
            elif request.content_tyoe.startswith('application/x-www-from-urlencoded'):
                request.__data__ = await request.post()
                logging.info('request form:%s' % str(request.__data__))
        return (await handler(request))
    return parse_data
async def response_factory(app,handler):
    async def response(request):
        logging.info('Response handler...')
        r = await handler(request)
        #treamResponse是aiohttp定义responsed的基类，及所有响应类型都继承自该类，主要为流式数据而设计
        if isinstance(r,web.StreamResponse):
            return r
        if isinstance(r,bytes):
            resp = web.response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(r,str):
            if r.startswith('redirect:'):      #检测到字符串则返回True，否则返回False
                return web.HTTPFount(r[9:]) #把r字符串之前的“redirect：”去掉
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        if isinstance(r,dict):
            template = r.get('__template__')
            if template is None:
                resp = web.Response(body=json.dumps(r,ensure_ascii=False,default=lambda o: o.__dict__).encode('utf-8'))
                resp.content_type='application/json;charset=utf-8'
                return resp
            else:
                r["__user__"] = request.__user__
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
                resp.cotent_type = 'text/html;charset=utf-8'
                return resp
        if isinstance(r,int) and r >= 100 and r< 600:
            return web.Response(t,str(m))
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset'
        return resp
    #上面6个if其实只用到了一个，准确的说只用到了半个。大家可以把用到的代码找出来，把没有用到的注释掉，如果程序能正常运行，那我觉得任务也就完成了
    #没用到的if语句块了解一下就好，等用到了再回过头来看，你就瞬间理解了。
    return response
#过滤时间么用于返回日志创建时间，显示在日志标题下面
def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year,dt.month,dt.day)
async def init(loop):
    await orm.create_pool(loop=loop,host='127.0.0.1',port=3306,user='root',password='111111',db='awesome')
    app = web.Application(loop=loop,middlewares=[logger_factory,auth_factory,response_factory])
    init_jinja2(app,filters=dict(datetime=datetime_filter))
    add_routes(app,'handlers')
    add_static(app)
    srv = await loop.create_server(app.make_handler(),'127.0.0.1',9000)
    logging.info('server started at  http://127.0.0.1:9000')
    return srv
loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()