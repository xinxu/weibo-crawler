import urllib, urllib2, cookielib, base64, re, json, hashlib, time, os
from lxml.html import fromstring
import base62

username = 'xinxu0x@gmail.com'
password = 'Whowareyou'
client = 'ssologin.js(v.1.3.18)'

def crawl(url, opener):
    print 'try crawling %s\n' % url
    f = opener.open(url)
    doc = fromstring(f.read())
    if doc is None:
        time.sleep(5)
        doc = fromstring(opener.open(url).read())
        if doc is None:
            print 'crawl %s error\n'
    return doc


def weibo_login():
    sha1 = lambda x : hashlib.sha1(x).hexdigest()
    cj = cookielib.CookieJar()
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
    resp = opener.open('http://login.sina.com.cn/sso/prelogin.php' + \
              '?entry=weibo&callback=sinaSSOController.preloginCallBack' + \
                '&su=%s&client=%s' %(base64.b64encode(username), client))
    respData = re.match(r'[^{]+({[^}]+})', resp.read()).group(1)
    jsonRespData = json.loads(respData)
    postData = {'entry' : 'weibo',
                'gateway' : 1,
                'from' : '',
                'savestate' : 7,
                'useticket' : 1,
                'ssosimplelogin' : 1,
                'su' : base64.b64encode(urllib.quote(username)),
                'service' : 'miniblog',
                'servertime' : jsonRespData['servertime'],
                'nonce' : jsonRespData['nonce'],
                'pwencode' : 'wsse',
                'sp' : sha1(sha1(sha1(password)) + \
                        str(jsonRespData['servertime']) + \
                        jsonRespData['nonce']),
                'encoding' : 'UTF-8',
                'url' :  'http://weibo.com/ajaxlogin.php?framelogin=1&callback=parent.sinaSSOController.feedBackUrlCallBack',
                'returntype' : 'META'}
    request = urllib2.Request('http://login.sina.com.cn/sso/login.php?client=%s' % client, urllib.urlencode(postData))
    loginData = opener.open(request)
    loginUrl = re.search(r'replace\(\'([^\']+)\'', loginData.read()).group(1)
    loginResult = opener.open(loginUrl).read()
    if (re.search(r'\"result\":true', loginResult) == None):
        raise 'login failed'
    print loginResult
    return opener

class WeiboParser(object):
    def __init__(self, opener, uid, wid):
        self.opener = opener
        self.uid = uid
        self.wid = wid
        self.mid = base62.str2mid(wid)

    def parse_all(self):
        result = {}
        result['userinfo'] = self.parse_user_info()
        result['comments'] = self.parse_comment()
        result['reposts'] = self.parse_repost()
        return result

    def parse_repost(self):
        page = 1
        result = []
        while (self.parse_repost_page(page, result)):
            page += 1
        return result

    def parse_comment(self):
        page = 1
        result = []
        while (self.parse_comment_page(page, result)):
            page += 1
        return result

    def parse_user_info(self):
        url = 'http://www.weibo.com/%s/%s' % (self.uid, self.wid)
        info = {}
        doc = crawl(url, self.opener)
        if doc is None:
            return {}
        inner_doc = self.get_inner_doc(doc, 'pl_content_personInfo')
        if inner_doc is None:
            return {}
        get_num = lambda x : inner_doc.xpath(
                '//strong[@node-type="%s"]/text()' % x)[0]
        info['follow'] = get_num('follow')
        info['fans'] = get_num('fans')
        info['weibo'] = get_num('weibo')
        info['city'] = inner_doc.xpath('//p[@class="city"]/text()')[0]
        return info

    def parse_repost_page(self, page, result):
        url = 'http://weibo.com/aj/mblog/info/big?id=%s&page=%s&_t=0' % \
                (self.mid, page)
        print url
        json_str = self.opener.open(url).read()
        if json_str is None:
            return False
        json_obj = json.loads(json_str)
        doc = fromstring(json_obj['data']['html'])
        repost_list = doc.xpath('//dl[@class="comment_list W_linecolor clearfix"]')
        if len(repost_list) == 0:
            return False
        for node in repost_list:
            result.append(self.parse_node(node))
        page_node = doc.xpath('//a[@class="W_btn_a"]')
        if (len(page_node) == 0):
            return False
        # last page
        if (len(page_node) < 2 and page != 1):
            return False
        return True

    def parse_comment_page(self, page, result):
        url = 'http://weibo.com/aj/comment/big?id=%s&page=%s&_t=0' % \
                (self.mid, page)
        print url
        json_str = self.opener.open(url).read()
        if json_str is None:
            return False
        json_obj = json.loads(json_str)
        doc = fromstring(json_obj['data']['html'])
        comment_list = doc.xpath('//dl[@class="comment_list W_linecolor clearfix"]')
        for node in comment_list:
            result.append(self.parse_node(node))
        page_node = doc.xpath('//a[@class="W_btn_a"]')
        if (len(page_node) == 0):
            return False
        # last page
        if (len(page_node) < 2 and page != 1):
            return False
        return True

    def parse_node(self, node):
        di = {}
        dd = node.xpath('./dd')[0]
        user_node = node.xpath('./dd/a')[0]
        di['content'] = dd.text_content().split('\n\t')[1];
        di['mid'] = node.xpath('./@mid')[0]
        di['uname'] = user_node.xpath('./@title')[0]
        di['uid'] = user_node.xpath('./@usercard')[0].split('=')[1]
        di['wid'] = base62.mid2str(di['mid'])
        return di

    def get_inner_doc(self, doc, pid):
        texts = doc.xpath('//text()')
        for text in texts:
            m = re.match(r'STK && STK\.pageletM && STK\.pageletM\.view\(({[^}]+})\)', text)
            if m is not None:
                innerHtml = json.loads(m.group(1))
                if innerHtml['pid'] == pid:
                    return fromstring(innerHtml['html'])
# main function
def recursive_run(uid, wid):
    def create_cache(depth):
        ret = {}
        ret['depth'] = depth
        ret['count'] = 0
        ret['list'] = list()
        return ret
    def record(depth, cache):
        with open('%s/%s.json' % (dir_str, depth), 'w') as f:
            f.write(json.dumps(cache))
    dir_str = '%s/%s' % (uid, wid)
    print dir_str
    try:
        os.makedirs(dir_str)
    except:
        pass
    opener = weibo_login()

    total_count = 0
    depth = 0
    parser = WeiboParser(opener, uid, wid)
    cache = create_cache(depth)
    page = parser.parse_all()
    cache['list'].append(page)
    cache['count'] = len(page['reposts'])
    while (cache['count'] > 0):
        total_count += cache['count']
        record(depth, cache)
        depth += 1
        new_cache = new_cache(depth)
        for page in cache['list']:
            for repost in page['reposts']:
                parser = WeiboParser(opener, repost['uid'], repost['wid'])
                page = parser.parse_all()
                new_cache['list'].append(page)
                new_cache['count'] = len(page['reposts'])
        cache = new_cache
    with open('%s/total.txt' % dir_str, 'w') as f:
        f.write('total count of repost is %d\n' % total_count)

if __name__ == '__main__':
    uid = '1866867923'
    wid = 'y7Dbft5Fq'
    recursive_run(uid, wid)

