#!/usr/bin/python
# -*- coding: utf-8 -*-
# #############################################################################
#    Copyright (C) 2018 manatlan manatlan[at]gmail(dot)com
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 2 only.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# https://github.com/manatlan/reqman
# #############################################################################
import yaml         # see pip
import os,json,sys,httplib,urllib,ssl,sys,urlparse,glob,cgi,socket,re

try: # colorama is optionnal

    from colorama import init,Fore,Style
    init()

    cy=lambda t: Fore.YELLOW+Style.BRIGHT + t + Fore.RESET+Style.RESET_ALL if t else None
    cr=lambda t: Fore.RED+Style.BRIGHT + t + Fore.RESET+Style.RESET_ALL if t else None
    cg=lambda t: Fore.GREEN+Style.BRIGHT + t + Fore.RESET+Style.RESET_ALL if t else None
    cb=lambda t: Fore.CYAN+Style.BRIGHT + t + Fore.RESET+Style.RESET_ALL if t else None
    cw=lambda t: Fore.WHITE+Style.BRIGHT + t + Fore.RESET+Style.RESET_ALL if t else None
except:
    cy=lambda t: t
    cr=lambda t: t
    cg=lambda t: t
    cb=lambda t: t
    cw=lambda t: t


def u(txt):
    """ decode txt to unicode """
    if txt and isinstance(txt,basestring):
        if type(txt) != unicode:
            try:
                return txt.decode("utf8")
            except:
                try:
                    return txt.decode("cp1252")
                except:
                    return unicode(txt)
    return txt


def ub(txt):
    """ same as u, but assume if decode trouble -> it's binary, and so return
        a string that represents the BINARY STUFF, to be able to display it
    """
    try:
        return u(txt)
    except:
        return "*** BINARY SIZE(%s) ***" % len(txt) #TODO: not great for non-response body


def prettyJson(txt):
    try:
        return json.dumps( json.loads( txt ), indent=4, sort_keys=True )
    except:
        return txt

class NotFound: pass

def jpath(elem, path):
    for i in path.strip(".").split("."):
        try:
            if type(elem)==list:
                elem= elem[ int(i) ]
            else:
                elem= elem.get(i,NotFound)
        except (ValueError,IndexError) as e:
            return NotFound
    return elem


class RMException(Exception):pass

###########################################################################
## http request/response
###########################################################################

COOKIEJAR=None

class Request:
    def __init__(self,protocol,host,port,method,path,body=None,headers={}):
        global COOKIEJAR
        self.protocol=protocol
        self.host=host
        self.port=port
        self.method=method
        self.path=path
        self.body=body
        self.headers=headers

        if COOKIEJAR:
            self.headers["cookie"]=COOKIEJAR

        if self.host and self.protocol:
            self.url="%s://%s%s" % (
                self.protocol,
                self.host+(":%s"%self.port if self.port else ""),
                self.path
            )

    def __repr__(self):
        return cy(self.method)+" "+self.path

class Response:
    def __init__(self,status,body,headers):
        global COOKIEJAR
        self.status = status
        self.content = ub(body)
        self.headers = dict(headers)

        if "set-cookie" in self.headers:
            COOKIEJAR = self.headers['set-cookie']

    def __repr__(self):
        return "%s" % (self.status)


def http(r):
    #TODO: cookies better handling with urllib2 ?!
    try:
        if r.protocol=="https":
            cnx=httplib.HTTPSConnection(r.host,r.port,context=ssl._create_unverified_context()) #TODO: ability to setup a verified ssl context ?
        else:
            cnx=httplib.HTTPConnection(r.host,r.port)
        cnx.request(r.method,r.path,r.body,r.headers)
        r=cnx.getresponse()
        return Response( r.status,r.read(),r.getheaders() )
    except socket.error:
        raise RMException("Server is down (%s)?" % ((r.host+":%s" % r.port) if r.port else r.host))


#= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #=
# http with urllib2 / but remove COOKIEJAR from Request/Response
# don't works well with 302 (coz urllib resolves them)
#= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #=
#~ import cookielib, urllib2

#~ # install an urlopener which handle cookies
#~ cookiejar = cookielib.CookieJar()
#~ opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookiejar))
#~ urllib2.install_opener(opener)

#~ def http(r):
    #~ try:
        #~ request = urllib2.Request( r.url, r.body, r.headers)
        #~ request.get_method = lambda: r.method
        #~ res=urllib2.urlopen(request, context=ssl._create_unverified_context())
    #~ except urllib2.HTTPError as err:
       #~ if err.code >= 400: # that's not errors ;-)
           #~ res=err
       #~ else:
           #~ raise
    #~ return Response( res.code, res.read(), res.headers )
#~ #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #=
#= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #= #=

###########################################################################
## Reqs manage
###########################################################################

class Test(int):
    """ a boolean with a name """
    def __new__(cls, name,value):
        s=super(Test, cls).__new__(cls, value)
        s.name = name
        return s

class TestResult(list):
    def __init__(self,req,res,tests):
        self.req=req
        self.res=res
        results=[]
        for test in tests:
            what,value = test.keys()[0],test.values()[0]

            testname = "%s = %s" % (what,value)
            if what=="status":  result = int(value)==int(self.res.status)
            elif what=="content": result = value in self.res.content
            elif what.startswith("json."):
                try:
                    jzon=json.loads(self.res.content)
                    val=jpath(jzon,what[5:])
                    val=None if val == NotFound else val
                    result = (value == val)
                except:
                    result=False
            else: result = (value in self.res.headers.get(what,""))
            #TODO: test if header is just present

            results.append( Test(testname,result) )

        list.__init__(self,results)

    def __str__(self):
        ll=[""]
        ll.append( cy("*")+u" %s --> %s " % (self.req,cw(str(self.res)) if self.res else cr(u"Not callable") ) )
        for t in self:
            ll.append( u"   - TEST: %s ? %s " %(t.name,cg("OK") if t==1 else cr("KO")) )
        txt = os.linesep.join(ll)
        return txt.encode( sys.stdout.encoding if sys.stdout.encoding else "utf8")

def getVar(env,var):
    if var in env:
        return env[var]
    elif "|" in var:
        key,method=var.split("|",1)

        if key in env:
            content = env[key]
            return transform(content,env,method) if method else content
        else:
            raise RMException("Can't resolve "+key+" in : "+ ", ".join(env.keys()))

    elif "." in var:
        val=jpath(env,var)
        if val is NotFound:
            raise RMException("Can't resolve "+var+" in : "+ ", ".join(env.keys()))
        return val
    else:
        raise RMException("Can't resolve "+var+" in : "+ ", ".join(env.keys()))



def transform(content,env,methodName):
    if content and methodName:
        if methodName in env:
            code=getVar(env,methodName)
            try:
                exec "def DYNAMIC(x):\n" + ("\n".join(["  "+i for i in code.splitlines()])) in locals()
            except Exception as e:
                raise RMException("Error in declaration of method "+methodName+" : "+str(e))
            try:
                x=json.loads(content)
            except:
                x=content
            try:
                content=DYNAMIC( x )
            except Exception as e:
                raise RMException("Error in execution of method "+methodName+" : "+str(e))
        else:
            raise RMException("Can't find method "+methodName+" in : "+ ", ".join(env.keys()))
    return content


class Req(object):
    def __init__(self,method,path,body=None,headers={},tests=[],save=None,params={}):  # body = str ou dict ou None
        self.method=method.upper()
        self.path=path
        self.body=body
        self.headers=headers
        self.tests=tests
        self.save=save
        self.params=params

    def test(self,env=None):

        cenv = env.copy() if env else {}    # current env
        cenv.update( self.params )          # override with self params

        def rep(txt):
            if cenv and txt and isinstance(txt,basestring):
                for vvar in re.findall("\{\{[^\}]+\}\}",txt):
                    var=vvar[2:-2]

                    val=getVar(cenv,var)
                    if val is not None and isinstance(val,basestring):
                        if type(val)==unicode: val=val.encode("utf8")
                        txt=txt.replace( vvar , val.encode('string_escape'))

            return txt


        # path ...
        if cenv and (not self.path.strip().startswith("http")) and ("root" in cenv):
            h=urlparse.urlparse( cenv["root"] )
        else:
            h=urlparse.urlparse( self.path )
            self.path = h.path + ("?"+h.query if h.query else "")

        # headers ...
        headers=cenv.get("headers",{}).copy() if cenv else {}
        headers.update(self.headers)                        # override with self headers
        for k in headers:
            headers[k]=rep(headers[k])

        # body ...
        if self.body and not isinstance(self.body,basestring):
            body=json.dumps(self.body)
        else:
            body=self.body
        body=rep(body)

        req=Request(h.scheme,h.hostname,h.port,self.method,rep(self.path),body,headers)
        if h.hostname:

            tests=[]+cenv.get("tests",[]) if cenv else []
            tests+=self.tests                               # override with self tests

            tests=[{test.keys()[0]:rep(test.values()[0])} for test in tests]    # replace vars

            res=http( req )
            if self.save:
                try:
                    env[ self.save ]=json.loads(res.content)
                except:
                    env[ self.save ]=res.content

            return TestResult(req,res,tests)
        else:
            # no hostname : no response, no tests ! (missing reqman.conf the root var ?)
            return TestResult(req,None,[])

    def __repr__(self):
        return "<%s %s>" % (self.method,self.path)

class Reqs(list):
    def __init__(self,fd):

        defs={}

        self.name = fd.name.replace("\\","/") if hasattr(fd,"name") else "String"
        try:
            l=yaml.load( u(fd.read()) )
        except Exception as e:
            raise RMException("YML syntax :"+e.problem+" at line "+str(e.context_mark and e.context_mark.line or ""))

        ll=[]
        if l:
            l=[l] if type(l)==dict else l

            for d in l:
                #--------------------------------------------------
                if "def" in d.keys():
                    callname = d["def"]
                    request = d
                    del request["def"]
                    defs[ callname ] = request
                    continue # just declare and nothing yet
                elif "call" in d.keys():
                    callname = d["call"]
                    del d["call"]
                    if callname in defs:
                        override = d.copy()
                        d.update( defs[callname] )
                        d.update( override )
                    else:
                        raise RMException("call a not defined def %s" % callname)
                #--------------------------------------------------
                mapkeys ={ i.upper():i for i in d.keys() }
                verbs= sorted(list(set(mapkeys).intersection(set(["GET","POST","DELETE","PUT","HEAD","OPTIONS","TRACE","PATCH","CONNECT"]))))
                if len(verbs)!=1:
                    raise RMException("no known verbs")
                else:
                    method=verbs[0]
                    body=d.get("body",None)
                    ll.append( Req(method,d.get( mapkeys[method],""),body,d.get("headers",[]),d.get("tests",[]),d.get("save",None),d.get("params",{})) )
        list.__init__(self,ll)



###########################################################################
## Helpers
###########################################################################
def listFiles(path,filters=(".yml") ):
    for folder, subs, files in os.walk(path):
        for filename in files:
            if filename.lower().endswith( filters ):
                yield os.path.join(folder,filename)


def loadEnv( fd, varenvs=[] ):
    try:
        env=yaml.load( u(fd.read()) ) if fd else {}
    except Exception as e:
        raise RMException("YML syntax :"+e.problem+" at line "+str(e.context_mark and e.context_mark.line or ""))
    for name in varenvs:
        if name not in env:
            raise RMException("the switch '-%s' is unknown ?!" % name)
        else:
            conf=env[name].copy()
            for k,v in conf.items():
                if k in env and type(env[k])==dict and type(v)==dict:
                    env[k].update( v )
                elif k in env and type(env[k])==list and type(v)==list:
                    env[k]+= v
                else:
                    env[k]=v
    return env

class HtmlRender(list):
    def __init__(self):
        list.__init__(self,[u"""
<meta charset="utf-8">
<style>
.ok {color:green}
.ko {color:red}
hr {padding:0px;margin:0px;height: 1px;border: 0;color: #CCC;background-color: #CCC;}
pre {padding:4px;border:1px solid black;background:white !important;overflow-x:auto;width:100%;max-height:300px}
div {background:#FFE;border-bottom:1px dotted grey;padding:4px;margin-left:16px}
span {cursor:pointer;}
ul {margin:0px;}
span:hover {background:#EEE;}
div.hide {background:inherit}
div.hide > ul > pre {display:none}
h3 {color:blue;}
</style>
"""])

    def add(self,html=None,tr=None):
        if tr is not None and tr.req and tr.res:
            html =u"""
<div class="hide">
    <span onclick="this.parentElement.classList.toggle('hide')" title="Click to show/hide details"><b>%s</b> %s : <b>%s</b></span>
    <ul>
        <pre title="the request">%s %s<hr/>%s<hr/>%s</pre>
        <pre title="the response">%s<hr/>%s</pre>
        %s
    </ul>
</div>
            """ % (
                tr.req.method,
                tr.req.path,
                tr.res.status,

                tr.req.method,
                tr.req.url,
                u"\n".join([u"<b>%s</b>: %s" %(k,v) for k,v in tr.req.headers.items()]),
                cgi.escape( prettyJson( u(tr.req.body or "")) ),

                u"\n".join([u"<b>%s</b>: %s" %(k,v) for k,v in tr.res.headers.items()]),
                cgi.escape( prettyJson( u(tr.res.content or "")) ),

                u"".join([u"<li class='%s'>%s</li>" % (t and u"ok" or u"ko",cgi.escape(t.name)) for t in tr ]),
                )
        if html: self.append( html )

    def save(self,name):
        open(name,"w+").write( os.linesep.join(self).encode("utf8") )

def main(params):
    try:
        # search for a specific env var (starting with "-")
        varenvs=[]
        for varenv in [i for i in params if i.startswith("-")]:
            params.remove( varenv )
            varenvs.append( varenv[1:] )

        # sort params as yml files
        ymls=[]
        paths=[]
        if not params: params=["."]
        for p in params:
            if os.path.isdir(p):
                paths.append(p)
                ymls+=sorted(list(listFiles(p)))
            elif os.path.isfile(p):
                paths.append( os.path.dirname(p) )
                if p.lower().endswith(".yml"):
                    ymls.append(p)
                else:
                    raise RMException("not a yml file") #TODO: better here
            else:
                raise RMException("bad param: %s" % p) #TODO: better here


        # choose first reqman.conf under choosen files
        rc=None
        folders=list(set(paths))
        folders.sort( key=lambda i: i.count("/"))
        for f in folders:
            if os.path.isfile( os.path.join(f,"reqman.conf") ):
                rc=os.path.join(f,"reqman.conf")

        #if not, take the local reqman.conf
        if rc is None and os.path.isfile( "reqman.conf" ): rc="reqman.conf"


        # load env !
        env=loadEnv( file(rc) if rc else None, varenvs )

        # hook oauth2
        if "oauth2" in env: #TODO: should found a clever way to setup/update vars in env ! to be better suitable
            up = urlparse.urlparse(env["oauth2"]["url"])
            req=Request(up.scheme,up.hostname,up.port,"POST",up.path,urllib.urlencode(env["oauth2"]["params"]),{'Content-Type': 'application/x-www-form-urlencoded'})
            res=http(req)
            token=json.loads(res.content)
            env["headers"]["Authorization"] = token["token_type"]+" "+token["access_token"]
            print cy("OAuth2 TOKEN: %s" % env["headers"]["Authorization"])


        # and make tests
        all=[]
        hr=HtmlRender()
        for f in [Reqs(file(i)) for i in ymls]:
            print cb(f.name)
            hr.add("<h3>%s</h3>"%f.name)
            for t in f:
                tr=t.test( env ) #TODO: colorful output !
                print tr
                hr.add( tr=tr )
                all+=tr

        ok,total=len([i for i in all if i]),len(all)

        hr.add( "<title>Result: %s/%s</title>" % (ok,total) )
        hr.save("reqman.html")

        print
        print "RESULT: ",(cg if ok==total else cr)("%s/%s" % (ok,total))
        return total - ok
    except RMException as e:
        print
        print "ERROR: %s" % e
        return -1
    except KeyboardInterrupt as e:
        print
        print "ERROR: process interrupted"
        return -1

if __name__=="__main__":
    sys.exit( main(sys.argv[1:]) )
