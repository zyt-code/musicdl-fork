'''
Function:
    Implementation of BuguyyMusicClient: https://buguyy.top/
Author:
    Zhenchao Jin
WeChat Official Account (微信公众号):
    Charles的皮卡丘
'''
import os
import re
import copy
from .base import BaseMusicClient
from urllib.parse import urlencode
from rich.progress import Progress
from ..utils import legalizestring, isvalidresp, usesearchheaderscookies, resp2json, safeextractfromdict, usedownloadheaderscookies, AudioLinkTester, WhisperLRC, QuarkParser


'''BuguyyMusicClient'''
class BuguyyMusicClient(BaseMusicClient):
    source = 'BuguyyMusicClient'
    def __init__(self, **kwargs):
        super(BuguyyMusicClient, self).__init__(**kwargs)
        if not self.quark_parser_config.get('cookies'): self.logger_handle.warning(f'{self.source}.__init__ >>> "quark_parser_config" is not configured, so song downloads are restricted and only mp3 files can be downloaded.')
        self.default_search_headers = {
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "origin": "https://buguyy.top",
            "priority": "u=1, i",
            "referer": "https://buguyy.top/",
            "sec-ch-ua": "\"Chromium\";v=\"142\", \"Google Chrome\";v=\"142\", \"Not_A Brand\";v=\"99\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        }
        self.default_download_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
        }
        self.default_headers = self.default_search_headers
        self._initsession()
    '''_download'''
    @usedownloadheaderscookies
    def _download(self, song_info: dict, request_overrides: dict = None, downloaded_song_infos: list = [], progress: Progress = None, song_progress_id: int = 0):
        if song_info['use_quark_default_download_headers']:
            request_overrides['headers'] = self.quark_default_download_headers
            return super()._download(song_info=song_info, request_overrides=request_overrides, downloaded_song_infos=downloaded_song_infos, progress=progress, song_progress_id=song_progress_id)
        else:
            return super()._download(song_info=song_info, request_overrides=request_overrides, downloaded_song_infos=downloaded_song_infos, progress=progress, song_progress_id=song_progress_id)
    '''_constructsearchurls'''
    def _constructsearchurls(self, keyword: str, rule: dict = None, request_overrides: dict = None):
        # init
        rule, request_overrides = rule or {}, request_overrides or {}
        # search rules
        default_rule = {'keyword': keyword}
        default_rule.update(rule)
        # construct search urls based on search rules
        base_url = 'https://a.buguyy.top/newapi/search.php?'
        page_rule = copy.deepcopy(default_rule)
        search_urls = [base_url + urlencode(page_rule)]
        self.search_size_per_page = self.search_size_per_source
        # return
        return search_urls
    '''_search'''
    @usesearchheaderscookies
    def _search(self, keyword: str = '', search_url: str = '', request_overrides: dict = None, song_infos: list = [], progress: Progress = None, progress_id: int = 0):
        # init
        request_overrides = request_overrides or {}
        # successful
        try:
            # --search results
            resp = self.get(search_url, **request_overrides)
            resp.raise_for_status()
            search_results = resp2json(resp=resp)['data']['list']
            for search_result in search_results:
                # --download results
                if 'id' not in search_result:
                    continue
                quark_download_urls, parsed_quark_download_url = [search_result.get('downurl', ''), search_result.get('ktmdownurl', '')], ''
                for quark_download_url in quark_download_urls:
                    try:
                        m = re.search(r"WAV#(https?://[^#]+)", quark_download_url)
                        quark_wav_download_url = m.group(1)
                        parsed_quark_download_url = QuarkParser.parsefromurl(quark_wav_download_url, **self.quark_parser_config)
                        break
                    except:
                        parsed_quark_download_url = ''
                        continue
                resp = self.get(f'https://a.buguyy.top/newapi/geturl2.php?id={search_result["id"]}', **request_overrides)
                if not isvalidresp(resp=resp) and not parsed_quark_download_url: continue
                download_result = resp2json(resp=resp)
                download_url = safeextractfromdict(download_result, ['data', 'url'], '')
                if not download_url and not parsed_quark_download_url: continue
                download_url_status = AudioLinkTester(headers=self.default_download_headers, cookies=self.default_download_cookies).test(download_url, request_overrides)
                parsed_quark_download_url_status = AudioLinkTester(headers=self.quark_default_download_headers, cookies=self.default_download_cookies).test(parsed_quark_download_url, request_overrides)
                if not download_url_status['ok'] and not parsed_quark_download_url_status['ok']: continue
                if parsed_quark_download_url_status['ok']:
                    download_url = parsed_quark_download_url
                    download_url_status = parsed_quark_download_url_status
                    download_result_suppl = AudioLinkTester(headers=self.quark_default_download_headers, cookies=self.default_download_cookies).probe(download_url, request_overrides)
                    if download_result_suppl['ext'] == 'NULL': download_result_suppl['ext'] = 'wav'
                    use_quark_default_download_headers = True
                else:
                    download_result_suppl = AudioLinkTester(headers=self.default_download_headers, cookies=self.default_download_cookies).probe(download_url, request_overrides)
                    if download_result_suppl['ext'] == 'NULL': download_result_suppl['ext'] = download_url.split('.')[-1].split('?')[0] or 'mp3'
                    use_quark_default_download_headers = False
                download_result['download_result_suppl'] = download_result_suppl
                # --lyric results
                lyric = safeextractfromdict(download_result, ['data', 'lrc'], '')
                if not lyric or '歌词获取失败' in lyric:
                    try:
                        if os.environ.get('ENABLE_WHISPERLRC', 'False').lower() == 'true':
                            lyric_result = WhisperLRC(model_size_or_path='small').fromurl(
                                download_url, headers=self.default_download_headers, cookies=self.default_download_cookies, request_overrides=request_overrides
                            )
                            lyric = lyric_result['lyric']
                        else:
                            lyric_result, lyric = dict(), 'NULL'
                    except:
                        lyric_result, lyric = dict(), 'NULL'
                else:
                    lyric_result, lyric = {'lyric': lyric}, lyric
                # --construct song_info
                try:
                    duration = '{:02d}:{:02d}:{:02d}'.format(*([0,0,0] + list(map(int, re.findall(r'\d+', safeextractfromdict(download_result, ['data', 'duration'], '')))))[-3:])
                except:
                    duration = '-:-:-'
                song_info = dict(
                    source=self.source, raw_data=dict(search_result=search_result, download_result=download_result, lyric_result=lyric_result), 
                    download_url_status=download_url_status, download_url=download_url, ext=download_result_suppl['ext'], file_size=download_result_suppl['file_size'], 
                    lyric=lyric, duration=duration, song_name=legalizestring(search_result.get('title', 'NULL'), replace_null_string='NULL'), 
                    singers=legalizestring(search_result.get('singer', 'NULL'), replace_null_string='NULL'), 
                    album=legalizestring(safeextractfromdict(download_result, ['data', 'album'], ''), replace_null_string='NULL'),
                    identifier=search_result['id'], use_quark_default_download_headers=use_quark_default_download_headers
                )
                # --append to song_infos
                song_infos.append(song_info)
                # --judgement for search_size
                if self.strict_limit_search_size_per_page and len(song_infos) >= self.search_size_per_page: break
            # --update progress
            progress.advance(progress_id, 1)
            progress.update(progress_id, description=f"{self.source}.search >>> {search_url} (Success)")
        # failure
        except Exception as err:
            progress.update(progress_id, description=f"{self.source}.search >>> {search_url} (Error: {err})")
        # return
        return song_infos