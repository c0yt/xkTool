# -*- coding: utf-8 -*-
import os
import sys
import requests
import time
from prettytable import PrettyTable
from hex2b64 import HB64
import RSAJS
import json
import bs4
import re
import pickle
from tqdm import tqdm

# 自定义Session类，继承自requests.Session
class Session(requests.Session):
    def request(self, *args, **kwargs):
        kwargs.setdefault('timeout', 60)  # 设置默认请求超时时间为60秒
        return super(Session, self).request(*args, **kwargs)  # 调用父类request方法

# 选课主类
class XkSystem:

    def __init__(self, user, pwd):
        self.session = Session()
        self.user = user
        self.pwd = pwd
        self.cookie_file = f'cookie_{user}.pkl'  # 为每个用户存储独立的cookie文件
        self.request_delay = 1.0
        self.host = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        }
        self.time = int(time.time() * 1000)
        self.xkkz_id = ''
        self.courses = []
        self.selectedCourses = []

    def _save_cookies(self):
        # 保存cookies到文件
        with open(self.cookie_file, 'wb') as f:
            pickle.dump(self.session.cookies, f)
        print('✅ Cookie已保存到本地')

    def _load_cookies(self):
        # 从文件加载cookies
        try:
            with open(self.cookie_file, 'rb') as f:
                self.session.cookies.update(pickle.load(f))
            return True
        except:
            return False

    def _check_login_status(self):
        # 检查登录状态
        try:
            r = self.session.get(f"{self.host}/xsxk/zzxkyzb_cxZzxkYzbIndex.html", headers=self.headers)
            return "请使用教务处教务系统的域名访问系统" not in r.text
        except:
            return False

    # 检测服务器延迟
    def _check_server_delay(self, host):
        try:
            start_time = time.time()  # 记录开始时间
            requests.get(host, timeout=10)  # 发送测试请求
            # print(r.request)
            delay = time.time() - start_time  # 计算延迟
            return delay * 1000  # 返回毫秒级的延迟
        except:
            return float('inf')  # 如果连接失败返回无穷大表示不可用

    def login(self,choice):
        # 从url.txt读取服务器列表
        try:
            with open('url.txt', 'r', encoding='utf-8') as f:
                hosts = [line.strip() for line in f if line.strip()]
            if not hosts:
                print("❌ url.txt 文件为空")
                exit_program("程序即将退出...", -1)
        except FileNotFoundError:
            print("❌ 未找到 url.txt 文件")
            exit_program("程序即将退出...", -1)
        except Exception as e:
            print(f"❌ 读取 url.txt 失败: {str(e)}")
            exit_program("程序即将退出...", -1)

        if choice == '2':
            print("\n可用的服务器列表:")
            for i, host in enumerate(hosts, 1):
                print(f"{i}. {host}")

            while True:
                try:
                    idx = int(input(f"\n请选择服务器 (1-{len(hosts)}): ")) - 1
                    if 0 <= idx < len(hosts):
                        self.host = hosts[idx]
                        break
                    print(f"❌ 请输入1-{len(hosts)}之间的数字")
                except ValueError:
                    print("❌ 请输入有效的数字")

            # 使用选定的服务器尝试登录
            if self._load_cookies():
                print("🔄 尝试使用保存的Cookie登录...")
                try:
                    if self._check_login_status():
                        print(f"✅ Cookie登录成功! 当前服务器: {self.host}")
                        return True
                except:
                    print("⚠️ Cookie登录失败，尝试账号密码登录...")

            try:
                print(f"🔄 正在尝试登录服务器 {self.host}")
                self._get_public()
                self._get_csrftoken()
                self._post_data()
                self._save_cookies()
                print('✅ 登录成功!')
                return True
            except requests.exceptions.RequestException as e:
                print(f'❌ 登录失败: 服务器连接超时')
                print('⚠️ 建议尝试自动选择服务器模式')
                exit_program("程序即将退出...", -1)
            except Exception as e:
                print('❌ 登录失败: 账号或密码错误')
                exit_program("程序即将退出...", -1)

        else:  # 自动选择服务器模式
            # 检测并排序服务器延迟
            print("🔄 正在检测服务器延迟...")
            server_delays = []
            for host in hosts:
                delay = self._check_server_delay(host)
                server_delays.append((host, delay))

            # 按延迟从小到大排序
            server_delays.sort(key=lambda x: x[1])
            for i, (host, delay) in enumerate(server_delays, 1):
                if delay == float('inf'):
                    print(f"❌ {host}: 连接失败")
                else:
                    print(f"✅ {host}: {delay:.1f}ms ✓")

            # 首先尝试使用保存的cookie
            if self._load_cookies():
                print("\n🔄 尝试使用保存的Cookie登录...")
                for host, delay in server_delays:
                    if delay == float('inf'):
                        continue
                    self.host = host
                    try:
                        if self._check_login_status():
                            print(f"✅ Cookie登录成功! 当前服务器: {host}")
                            return True
                    except:
                        continue
                print("⚠️ 保存的Cookie已失效，尝试重新登录...")

            # Cookie无效或不存在时，使用账号密码登录
            print("\n🔑 正在使用账号密码登录...")
            flag = 0  # 登录成功标志
            for host, delay in server_delays:
                if delay == float('inf'):  # 跳过不可用的服务器
                    continue
                self.host = host  # 设置当前主机
                try:
                    print(f"\n🔄 正在尝试登录服务器 {host}")
                    self._get_public()  # 获取公钥
                    self._get_csrftoken()  # 获取CSRF Token
                    self._post_data()  # 提交登录数据
                    flag = 1  # 标记登录成功
                    # 登录成功后保存cookie
                    self._save_cookies()
                    break  # 登录成功后跳出循环
                except requests.exceptions.RequestException as e:
                    print(f'服务器 {host} 响应超时，尝试下一个...')
                except Exception as e:
                    print('❌ 登录失败: 账号或密码错误')
                    break

            if flag == 1:  # 登录成功
                print('✅ 登录成功!')
                return True
            else:
                exit_program("❌ 程序终止: 登录失败", -1)

    def _get_public(self):
        try:
            url = self.host + '/xtgl/login_getPublicKey.html'
            r = self.session.get(url)
            self.pub = r.json()
            print('✅ 登录步骤一：获取公钥成功！')
        except Exception as e:
            print(f'❌ 登录步骤一：获取公钥失败: {str(e)}')

    def _get_csrftoken(self):
        try:
            url = self.host + '/xtgl/login_slogin.html'
            r = self.session.get(url)
            htm = bs4.BeautifulSoup(r.text, "html.parser")
            self.csrftoken = htm.select("#csrftoken")[0]["value"]
            print('✅ 登录步骤二：获取csrf token成功！')
        except Exception as e:
            print(f'❌ 登录步骤二：获取csrf token失败: {str(e)}')

    def _process_public(self, pwd):
        self.exponent = HB64().b642hex(self.pub['exponent'])
        self.modulus = HB64().b642hex(self.pub['modulus'])
        rsa = RSAJS.RSAKey()
        rsa.setPublic(self.modulus, self.exponent)
        cry_data = rsa.encrypt(pwd)
        return HB64().hex2b64(cry_data)

    def _post_data(self):
        ras_pw = self._process_public(self.pwd)
        url = self.host + '/xtgl/login_slogin.html'
        data = {
            'csrftoken': self.csrftoken,
            'language': "zh_CN",
            'yhm': self.user,
            'mm': ras_pw,
            'mm': ras_pw,
        }
        print('✅ 登录步骤三：正在提交登录请求')
        r = self.session.post(url, headers=self.headers, data=data)
        print('✅ 登录步骤四：正在校验服务器响应')
        pattern = r'用户名或密码不正确'
        if re.search(pattern, r.text) is not None:
            raise Exception('❌ 登录异常')

    def _prepare_userinfo(self, ignore_classtype=False):
        form = {}
        url_zzxk = self.host + '/xsxk/zzxkyzb_cxZzxkYzbIndex.html?gnmkdm=N253512&layout=default&su=' + self.user
        r = self.session.get(url=url_zzxk, headers=self.headers)

        if "本学期已选学分" not in r.text:
            print('❌ 当前未开放选课')
            return None

        htm = bs4.BeautifulSoup(r.text, "html.parser")  # 解析选课页面内容

        # 基本字段列表
        a = ['xqh_id', 'jg_id_1', 'zyh_id', 'zyfx_id', 'njdm_id', 'bh_id', 'xbm', 'xslbdm', 'ccdm', 'xsbj', 'xkxnm',
             'xkxqm']

        # 添加特殊课程需要的字段
        special_fields = ['mzm', 'xz']
        a.extend(special_fields)

        # 遍历所有字段并提取值
        for i in a:
            select_i = '#' + i
            try:
                form[i] = htm.select(select_i)[0]['value']
            except:
                # 如果找不到字段，设置默认值为空字符串
                form[i] = ''
                if i in special_fields:
                    print(f"⚠️ 未找到 {i} 参数，使用默认值")

        # 使用 jg_id_1 的值作为 jg_id
        form['jg_id'] = form.get('jg_id_1', '')

        # 检查是否只有一个选课类别
        nav_tabs = htm.select('.nav-tabs')

        if not nav_tabs:  # 只有一个页签的情况
            course_types = [{
                'kklxdm': htm.select('#firstKklxdm')[0]['value'],
                'xkkz_id': htm.select('#firstXkkzId')[0]['value'],
                'name': htm.select('#firstKklxmc')[0]['value']
            }]
        else:  # 多个页签的情况
            pattern = r'queryCourse\(this,\'(\d+)\',\'([A-Z0-9]+)\',.*?\>(.*?)\<\/a\>'
            course_types = []
            for match in re.finditer(pattern, r.text):
                course_types.append({
                    'kklxdm': match.group(1),
                    'xkkz_id': match.group(2),
                    'name': match.group(3)
                })

        url = self.host + '/xsxk/zzxkyzb_cxZzxkYzbDisplay.html?gnmkdm=N253512&su=' + self.user

        if not ignore_classtype:
            print('📚 可选课程类别:')
            for idx, course_type in enumerate(course_types):
                print(f"{idx} {course_type['name']}")
            mode = int(input('📝 请选择课程类别 (输入编号,从0开始): '))
            selected_type = course_types[mode]
            form['xkkz_id'] = selected_type['xkkz_id']
            self.xkkz_id = form['xkkz_id']
            form['kklxdm'] = selected_type['kklxdm']
            self.mode = selected_type['name']

        data = {
            "xkkz_id": self.xkkz_id,
            "xszxzt": "1",
            "kspage": "0",
            "jspage": "0"
        }
        r = self.session.post(url=url, data=data, headers=self.headers)  # 请求获取选课显示页面的内容
        htm = bs4.BeautifulSoup(r.text, 'html.parser')  # 解析选课显示页面内容
        # 从页面中提取更多的表单字段并存入表单字典
        form.setdefault('rwlx', htm.select('#rwlx')[0]['value'])
        form.setdefault('xkly', htm.select('#xkly')[0]['value'])
        form.setdefault('bklx_id', htm.select('#bklx_id')[0]['value'])
        form.setdefault('sfkknj', htm.select('#sfkknj')[0]['value'])
        form.setdefault('sfkkzy', htm.select('#sfkkzy')[0]['value'])
        form.setdefault('sfznkx', htm.select('#sfznkx')[0]['value'])
        form.setdefault('zdkxms', htm.select('#zdkxms')[0]['value'])
        form.setdefault('sfkxq', htm.select('#sfkxq')[0]['value'])
        form.setdefault('sfkcfx', htm.select('#sfkcfx')[0]['value'])
        form.setdefault('kkbk', htm.select('#kkbk')[0]['value'])
        form.setdefault('kkbkdj', htm.select('#kkbkdj')[0]['value'])
        form.setdefault('rlkz', htm.select('#rlkz')[0]['value'])
        form.setdefault('rlzlkz', htm.select('#rlzlkz')[0]['value'])
        form.setdefault('sfkgbcx', htm.select('#sfkgbcx')[0]['value'])
        form.setdefault('sfrxtgkcxd', htm.select('#sfrxtgkcxd')[0]['value'])
        form.setdefault('tykczgxdcs', htm.select('#tykczgxdcs')[0]['value'])
        form.setdefault('xkzgbj', htm.select('#xkzgbj')[0]['value'])
        form.setdefault('xklc', htm.select('#xklc')[0]['value'])

        self.form = form

        return form


    def _get_TmpList(self, filter_params=None):

        form = self.form  # 使用类中保存的form
        # 添加筛选参数
        if filter_params:
            if 'filter_list' in filter_params:
                for idx, item in enumerate(filter_params['filter_list']):
                    form[f'filter_list[{idx}]'] = item
            if 'sksj_list' in filter_params:
                for idx, item in enumerate(filter_params['sksj_list']):
                    form[f'sksj_list[{idx}]'] = item
            if 'yl_list' in filter_params:
                for idx, item in enumerate(filter_params['yl_list']):
                    form[f'yl_list[{idx}]'] = item
            if 'kcgs_list' in filter_params:  # 添加课程归属筛选
                for idx, item in enumerate(filter_params['kcgs_list']):
                    form[f'kcgs_list[{idx}]'] = item

        # 添加分页参数
        form['kspage'] = '1'
        form['jspage'] = '2000'
        form['jxbzb'] = ''

        course_url = self.host + '/xsxk/zzxkyzb_cxZzxkYzbPartDisplay.html?gnmkdm=N253512&su=' + self.user
        course_list = self.session.post(course_url, data=form)
        return json.loads(course_list.text)['tmpList']

    def _get_course_detail(self, form, kch_id):
        # 获取课程详细信息
        url = self.host + '/xsxk/zzxkyzbjk_cxJxbWithKchZzxkYzb.html?gnmkdm=N253512&su=' + self.user
        detail_form = {**form}  # 复制表单数据
        detail_form.update({
            'kch_id': kch_id,
            'bklx_id': self.form.get('bklx_id', '0'),
            'xkxnm': self.form.get('xkxnm', ''),
            'xkxqm': self.form.get('xkxqm', ''),
            'kklxdm': self.form.get('kklxdm', ''),
            'xkkz_id': self.form.get('xkkz_id', ''),
            'xkxskcgskg': 1
        })

        try:
            r = self.session.post(url=url, data=detail_form, headers=self.headers)
            return json.loads(r.text)
        except Exception as e:
            print(f"❌ 获取课程详情失败: {str(e)}")
            return []

    def _process_tmplist(self):
        # 添加筛选选项
        choice = input("📝 是否需要添加筛选条件？(可直接回车跳过，输入 y 添加筛选)：").strip().lower()
        filter_params = {}
        if choice == 'y':
            print("请选择筛选方式：")
            print("1. 按课程名筛选")
            print("2. 按上课时间筛选")
            print("3. 按课程归属筛选")
            print("4. 按余量筛选")

            choice = input("📝 请选择 (1-4): ").strip()

            if choice == '1':
                course_names = input("📝 请输入课程名关键字 (多个关键字用逗号分隔): ").strip()
                keywords = [name.strip() for name in course_names.split(',') if name.strip()]
                if keywords:
                    filter_params['filter_list'] = keywords
                    print(f"✅ 将筛选包含以下关键字的课程: {', '.join(keywords)}")
                else:
                    print("⚠️ 未输入有效的关键字，将显示所有课程")
            elif choice == '2':
                weekday = input("📝 请输入上课时间 (如：周一或星期一): ").strip()
                # 转换星期格式为数字
                weekday_map = {
                    '周一': '1', '星期一': '1',
                    '周二': '2', '星期二': '2',
                    '周三': '3', '星期三': '3',
                    '周四': '4', '星期四': '4',
                    '周五': '5', '星期五': '5',
                    '周六': '6', '星期六': '6',
                    '周日': '7', '星期日': '7',
                    '周天': '7', '星期天': '7'
                }
                if weekday in weekday_map:
                    filter_params['sksj_list'] = [weekday_map[weekday]]
                else:
                    print("❌ 输入格式错误，将不使用时间筛选")
            elif choice == '3':
                print("\n📝 请选择课程归属：")
                print("1. 人文社会科学")
                print("2. 自然科学与技术")
                print("3. 艺术与审美")
                print("4. 创新创业")
                
                kcgs_choice = input("📝 请选择 (1-5): ").strip()
                # 课程归属映射
                kcgs_map = {
                    '1': '1',  # 人文社会科学
                    '2': '2',  # 自然科学与技术
                    '3': '3',  # 艺术与审美
                    '4': '7'   # 创新创业
                }
                
                if kcgs_choice in kcgs_map:
                    filter_params['kcgs_list'] = [kcgs_map[kcgs_choice]]
                    kcgs_names = {
                        '1': '人文社会科学',
                        '2': '自然科学与技术',
                        '3': '艺术与审美',
                        '4': '创新创业'
                    }
                    print(f"✅ 将筛选{kcgs_names[kcgs_choice]}类课程")
                else:
                    print("❌ 输入无效，将不使用课程归属筛选")
            elif choice == '4':
                yl_choice = input("📝 请选择余量筛选条件 (1: 只显示有余量, 2: 只显示无余量): ").strip()
                if yl_choice == '1':
                    filter_params['yl_list'] = ['1']  # 有余量
                elif yl_choice == '2':
                    filter_params['yl_list'] = ['0']  # 无余量
                else:
                    print("❌ 输入无效，将不使用余量筛选")
            else:
                print("❌ 输入无效，将不使用筛选")

        # 获取课程列表
        tmp_list = self._get_TmpList(filter_params if filter_params else None)
        # 获取课程详情的时间间隔设置
        while True:
            time_input = input('📝 请设置获取课程详情的时间间隔(秒)，直接回车默认1秒: ').strip()
            if not time_input:  # 如果用户直接回车
                time_interval = 1.0
                print('✅ 已使用默认间隔：1秒')
                break
            try:
                time_interval = float(time_input)
                if time_interval < 1:
                    confirm = input('⚠️ 警告：间隔时间小于1秒可能导致请求被限制，建议设置大于等于1秒，是否继续？(y/N): ').strip().lower()
                    if confirm != 'y':
                        continue
                break
            except ValueError:
                print('❌ 请输入有效的数字')
                continue

        print('📚 可选课程列表:')

        # 创建PrettyTable对象
        table = PrettyTable()
        # 根据kklxdm决定显示课程性质还是课程归属
        column_names = ["序号", "课程名称"]
        if self.form.get('kklxdm') == "10":
            column_names.append("课程归属")
        else:
            column_names.append("课程性质")
        column_names.extend(["学分", "教师", "上课时间", "上课地点", "已选/容量", "状态"])
        table.field_names = column_names

        # 设置表格样式
        table.align = "l"  # 左对齐
        table.max_width = 50  # 限制每列最大宽度
        table.hrules = 1  # 显示横线

        # 获取已选课程列表
        url = self.host + '/xsxk/zzxkyzb_cxZzxkYzbChoosedDisplay.html?gnmkdm=N253512&su=' + self.user
        r = self.session.post(url=url, data=self.form, headers=self.headers)
        selected_list = json.loads(r.text)

        # 分别存储已选课程的教学班ID和课程号
        selected_jxb_ids = [item['jxb_id'] for item in selected_list]  # 用于显示状态

        # 存储课程信息
        course_info = []
        names = []
        index = 0

        # 遍历可选课程列表
        for item in tqdm(tmp_list, desc="📚 获取课程详情", ncols=100,
                         bar_format='{desc}: {percentage:3.0f}%|{bar:10}| {n_fmt}/{total_fmt}'):
            name = item['kcmc']
            
            # 获取该课程的教学班信息
            details = self._get_course_detail(self.form, item['kch_id'])
            if not details:
                continue

            # 添加课程名到names列表（如果还没有添加）
            if name not in names:
                names.append(name)

            # 添加延迟
            time.sleep(time_interval)

            # 检查是否有多个教学班
            has_multiple_classes = len(details) > 1

            # 遍历该课程的教学班
            for detail in details:
                try:
                    # 确保detail和item的教学班ID匹配
                    if detail.get('jxb_id') != item.get('jxb_id'):
                        continue

                    jxb_id = detail.get('jxb_id', '')

                    # 检查是否已选
                    is_selected = '✅' if jxb_id in selected_jxb_ids else ''

                    # 准备容量信息
                    capacity = detail.get('jxbrl', '')  # 课程容量
                    selected = item.get('yxzrs', '0')  # 从item中获取已选人数
                    capacity_info = f"{selected}/{capacity}" if capacity else ''

                    # 确定课程状态
                    status = is_selected
                    if not status:  # 如果未选，显示其他状态
                        try:
                            selected_num = int(selected)
                            capacity_num = int(capacity)
                            if selected_num >= capacity_num:
                                status = '❌'
                            elif selected_num >= capacity_num * 0.8:
                                status = '⚠️'
                            elif selected_num < capacity_num:
                                status = '🉑'
                        except ValueError:
                            status = '❓'

                    # 处理教师信息
                    teacher_info = detail.get('jsxx', '')
                    teacher_name = ''
                    if teacher_info:
                        parts = teacher_info.split('/')
                        if len(parts) >= 2:
                            teacher_name = parts[1]
                        else:
                            teacher_name = teacher_info

                    row = [
                        index,  # 序号
                        name,  # 课程名称
                    ]
                    # 根据kklxdm决定添加课程性质还是课程归属
                    if self.form.get('kklxdm') == "10":
                        row.append(detail.get('kcgsmc', '通识选修课'))  # 课程归属，默认为通识选修课
                    else:
                        row.append(detail.get('kcxzmc', ''))  # 课程性质
                    row.extend([
                        item.get('xf', ''),  # 学分
                        teacher_name,  # 教师姓名
                        detail.get('sksj', '').replace('<br/>', '\n'),  # 上课时间
                        detail.get('jxdd', '').replace('<br/>', '\n'),  # 上课地点
                        capacity_info,  # 已选/容量
                        status  # 状态
                    ])

                    # 添加行到表格
                    table.add_row(row)

                    # 添加选课信息，确保与显示的序号对应
                    course_info.append({
                        'index': index,  # 添加序号信息
                        'kch_id': item['kch_id'],
                        'cxbj': item['cxbj'],
                        'fxbj': item['fxbj'],
                        'do_jxb_id': detail.get('do_jxb_id', ''),
                        'jxb_id': detail.get('jxb_id', ''),
                        'has_multiple_classes': has_multiple_classes,  # 添加标记
                        'name': name  # 添加课程名称
                    })

                    index += 1

                except KeyError:
                    continue

        # 打印表格
        print(table)
        
        # 添加状态说明
        print("状态说明：✅ -> 已选 ❌ -> 已满 ⚠️ -> 即满(>80%) 🉑 -> 可选 ❓ -> 未知")
        print(f"\n✨ 找到了 {len(names)} 门课程，共 {index} 个教学班")

        return course_info, names

    def run(self):
        url_xuanke = self.host + '/xsxk/zzxkyzbjk_xkBcZyZzxkYzb.html?gnmkdm=N253512&su=' + self.user
        self.current_selected = len(self.selectedCourses)

        # 检查是否开放选课并获取课程类别
        form = self._prepare_userinfo()
        if form is None:  # 如果未开放选课，返回上一级菜单
            return

        # 获取已选课程列表
        url_selected = self.host + '/xsxk/zzxkyzb_cxZzxkYzbChoosedDisplay.html?gnmkdm=N253512&su=' + self.user
        r = self.session.post(url=url_selected, data=form, headers=self.headers)
        selected_list = json.loads(r.text)
        selected_kch_ids = [item['kch'] for item in selected_list]  # 记录已选课程的kch

        # 获取可选课程列表
        tmp_list = self._get_TmpList()
        if not tmp_list:
            print("❌ 没有找到符合条件的课程")
            return

        # 创建PrettyTable对象并显示课程列表
        course_info, names = self._process_tmplist()

        if not names:
            print("❌ 没有找到符合条件的课程")
            return

        # 手动选课逻辑
        while True:
            try:
                num_courses = int(input("\n📝 请输入抢课数量(-1退出): "))
                if num_courses == -1:
                    print("❌ 已取消选课")
                    return
                if num_courses <= 0:
                    print("❌ 数量必须大于0")
                    continue
                if num_courses > 2:  # 修改这里，限制最多2门课
                    print("❌ 最多只能选择2门课程")
                    continue
                if num_courses > len(names):
                    print(f"❌ 可选课程只有 {len(names)} 门")
                    continue
                break
            except ValueError:
                print("❌ 请输入有效的数字")

        # 存储用户选择的课程信息
        selected_courses = []
        print("📝 请输入要抢的课程序号(从0开始):")

        for i in range(num_courses):
            while True:
                try:
                    course_index = int(input(f"请输入第 {i + 1} 门课的序号 (-1退出): "))
                    if course_index == -1:
                        print("❌ 已取消选课")
                        return
                    if course_index < 0 or course_index >= len(course_info):
                        print(f"❌ 序号必须在 0-{len(course_info) - 1} 之间")
                        continue
                    
                    # 检查是否已经选择过这个教学班
                    if course_index in [x['index'] for x in selected_courses]:
                        print("❌ 这个教学班已经选择过了")
                        continue

                    # 获取当前选择的课程信息
                    course_data = course_info[course_index]
                    
                    # 检查是否已经选过这门课
                    if course_data['kch_id'] in selected_kch_ids:
                        print(f"❌ 你已经选过 {course_data['name']} 这门课了")
                        continue

                    # 添加选课信息
                    selected_courses.append({
                        'index': course_index,
                        'info': course_data,
                        'name': course_data['name']
                    })
                    
                    break
                except ValueError:
                    print("❌ 请输入有效的数字")

        # 确认选课信息
        print("\n你选择的课程是:")
        for course in selected_courses:
            print(f"- {course['name']}")

        choice = input("\n要开始选课吗? (Y/n): ")  # 默认是Y
        if choice and choice.lower() == 'n':  # 只有明确输入n才取消
            return

        # 让用户设置选课延迟
        while True:
            try:
                delay_input = input("📝 请设置选课请求间隔(秒)，建议0.5-2秒 [默认1.0]: ").strip()
                self.request_delay = float(delay_input) if delay_input else 1.0

                if self.request_delay < 0:
                    print("❌ 延迟时间不能为负数")
                    continue
                if self.request_delay > 5:
                    confirm = input("⚠️ 延迟时间较长，是否继续？(y/N): ")  # 默认是N
                    if not confirm or confirm.lower() != 'y':  # 需要明确输入y才继续
                        continue
                break
            except ValueError:
                print("❌ 请输入有效的数字")

        print("\n🔄 开始选课...")
        success_count = 0

        # 单线程选课逻辑
        for course in selected_courses:
            form = {**self.form, **course['info']}
            form['qz'] = '0'
            
            while True:
                try:
                    result = self._click_xuanke(url_xuanke, form, course['name'])
                    if result:  # 如果选课成功
                        success_count += 1
                        break
                    else:
                        print(f"❌ {course['name']} 选课失败")
                        time.sleep(self.request_delay)
                        break
                except Exception as e:
                    print(f"❌ {course['name']} 选课出错: {str(e)}")
                    time.sleep(self.request_delay)

        print("\n--------------------------------")
        print('✅ 选课完成!')
        print(f'✅ 成功选课 {success_count} 门')
        if success_count > 0:
            print(f'✅ 新选课程: {", ".join(self.selectedCourses[self.current_selected:])}')
        return

    def _click_xuanke(self, url_xuanke, form, name):
        """单次选课尝试，返回是否成功"""
        print(f'🔄 正在尝试选择 {name} ...')
        try:
            # 如果是多个教学班的情况，直接使用已有的do_jxb_id
            if form.get('has_multiple_classes'):
                print(f"🔄 检测到 {name} 含多个教学班，正在处理 ...")
                main_do_jxb_id = form['do_jxb_id']
                form['jxb_ids'] = main_do_jxb_id
            else:
                # 获取主课程信息
                url = self.host + '/xsxk/zzxkyzbjk_cxJxbWithKchZzxkYzb.html?gnmkdm=N253512&su=' + self.user
                r = self.session.post(url=url, data=form, headers=self.headers)
                course_info = r.json()
                if course_info and len(course_info) > 0:
                    main_do_jxb_id = course_info[0]['do_jxb_id']
                    form['jxb_ids'] = main_do_jxb_id
                else:
                    print(f'❌ {name}: 未能获取最新教学班信息')
                    return False

            time.sleep(self.request_delay)
            r = self.session.post(url=url_xuanke, data=form, headers=self.headers)
            result = r.json()

            if result.get('flag') == '1':
                self.selectedCourses.append(name)
                print(f'✅ 选课成功! - {name}')
                return True
            elif result.get('flag') == '-1':
                print(f'❌ {name}: 课程人数已满')
            elif result.get('flag') == '0':
                print(f'❌ {name}: {result.get("msg", "课程冲突")}')
            else:
                print(f'❗ {name}: {result.get("msg", "未知错误")}')
            return False
            
        except Exception as e:
            print(f'❌ 服务器响应异常 - {name}: {str(e)}')
            return False

    def display_selected(self):
        """查看已选课程"""
        # 检查是否开放选课
        form = self._prepare_userinfo(ignore_classtype=True)
        if form is None:  # 如果未开放选课，返回上一级菜单
            return

        url = self.host + '/xsxk/zzxkyzb_cxZzxkYzbChoosedDisplay.html?gnmkdm=N253512&su=' + self.user
        r = self.session.post(url=url, data=form, headers=self.headers)
        selected_list = json.loads(r.text)

        if not selected_list:
            print('\n❌ 当前没有已选课程')
            return

        # 创建PrettyTable对象
        table = PrettyTable()
        table.field_names = ["序号", "课程名称", "课程号", "教学班ID", "教师", "上课时间", "上课地点"]

        # 设置表格样式
        table.align = "l"  # 左对齐
        table.max_width = 50  # 限制每列最大宽度
        table.hrules = 1  # 显示横线

        # 添加数据到表格
        for idx, item in enumerate(selected_list):
            # 处理教师信息 - 只保留教师姓名
            teacher_info = item['jsxx']
            teacher_name = ''
            if teacher_info:
                parts = teacher_info.split('/')
                if len(parts) >= 2:
                    teacher_name = parts[1]  # 取中间部分作为教师姓名
                else:
                    teacher_name = teacher_info  # 如果格式不匹配，使用原始字符串

            row = [
                idx,  # 序号
                item['jxbmc'],  # 课程名称
                item['kch'],  # 课程号
                item['jxb_id'],  # 教学班ID
                teacher_name,  # 只显示教师姓名
                item.get('sksj', '').replace('<br/>', '\n'),  # 上课时间
                item.get('jxdd', '').replace('<br/>', '\n'),  # 上课地点
            ]
            table.add_row(row)

        print('\n📚 已选课程列表:')
        print(table)
        print(f'📚 已选课程总数: {len(selected_list)} 门')

    def drop_course(self):
        """退课功能"""
        # 检查是否开放选课
        form = self._prepare_userinfo(ignore_classtype=True)
        if form is None:  # 如果未开放选课，返回上一级菜单
            return

        url = self.host + '/xsxk/zzxkyzb_cxZzxkYzbChoosedDisplay.html?gnmkdm=N253512&su=' + self.user
        r = self.session.post(url=url, data=form, headers=self.headers)
        selected_list = json.loads(r.text)

        if not selected_list:
            print('\n❌ 当前没有已选课程')
            return

        # 创建PrettyTable对象
        table = PrettyTable()
        table.field_names = ["序号", "课程名称", "教师", "上课时间"]

        # 设置表格样式
        table.align = "l"
        table.max_width = 50
        table.hrules = 1

        # 添加数据到表格（简化显示）
        for idx, item in enumerate(selected_list):
            teacher_info = item['jsxx']
            teacher_name = ''
            if teacher_info:
                parts = teacher_info.split('/')
                if len(parts) >= 2:
                    teacher_name = parts[1]
                else:
                    teacher_name = teacher_info

            row = [
                idx,
                item['jxbmc'],
                teacher_name,
                item.get('sksj', '').replace('<br/>', '\n'),
            ]
            table.add_row(row)

        print('\n📚 可退课程列表:')
        print(table)

        while True:
            try:
                idx = int(input('📝 请输入要退课的序号 (-1取消): '))
                if idx == -1:
                    print('❌ 已取消退课')
                    return
                if 0 <= idx < len(selected_list):
                    course = selected_list[idx]
                    confirm = input(f'⚠️ 确认要退 {course["jxbmc"]} 吗? (1:确认 0:取消): ')
                    if confirm == '1':
                        self._tuike(course['jxb_id'], course['kch'])
                    else:
                        print('❌ 已取消退课')
                    break
                else:
                    print(f'❌ 序号必须在 0-{len(selected_list) - 1} 之间')
            except ValueError:
                print('❌ 请输入有效的数字')

    def _tuike(self, jxb_id, kch_id):
        tuike_url = self.host + '/xsxk/tjxkyzb_tuikBcTjxkYzb.html?gnmkdm=N253511&su=' + self.user
        form = {
            'jxb_ids': jxb_id,
            'kch_id': kch_id,
            'xkkz_id': self.xkkz_id,
            'qz': 0
        }
        form = {**form, **self.form}
        r = self.session.post(url=tuike_url, data=form, headers=self.headers)
        # print(r.text)
        if r.text == '"1"':
            print('✅ 退课成功!')


def print_menu():
    """打印主菜单"""
    print("\n" + "=" * 42)
    print("📚 选课系统菜单:")
    print("1. 普通选课(支持筛选)")
    print("2. 退课")
    print("3. 查看已选课程")
    print("0. 退出")
    print("=" * 42)


def exit_program(message=None, exit_code=0):
    """友好的程序退出函数"""
    if message:
        print(message)
    os.system('pause')  # 暂停让用户看到信息
    sys.exit(exit_code)


if __name__ == '__main__':
    os.system("chcp 65001 && cls")  # 设置控制台为UTF-8编码并清屏
    print("=" * 42)
    print('''正方选课助手 V_1.0.4          
------------------------------------------

🌐 服务器选择:
1. 自动选择服务器
2. 手动指定服务器
0. 退出程序

------------------------------------------
Author：null
GitHub：https://github.com/c0yt
⚠️ 仅供个人学习使用，禁止用于个人盈利！''')
    print("=" * 42)

    while True:
        choice = input("\n📝 请选择服务器连接方式 (0-2): ").strip()
        
        if choice == "0":
            exit_program('👋 感谢使用，再见！')
        elif choice in ["1", "2"]:
            break
        else:
            print("❌ 无效的选择，请重试")

    print('\n🔑 请输入账号密码:')
    userName = input('👤 学号: ').strip()
    passWord = input('🔒 密码: ').strip()
    if not userName or not passWord:
        exit_program("❌ 账号密码不能为空!", 1)
    
    test = XkSystem(userName, passWord)

    # 尝试登录
    if not test.login(choice):
        exit_program("❌ 登录失败，程序退出", 1)

    print("\n🔑 正在进入选课系统，请稍后...")

    while True:
        print_menu()
        choice = input("\n📝 请选择功能: ")

        if choice == "1":
            test.run()
        elif choice == "2":
            test.drop_course()
        elif choice == "3":
            test.display_selected()
        elif choice == "0":
            exit_program('👋 感谢使用，再见！')
        else:
            print("❌ 无效的选择，请重试")

        # 统一在循环末尾处理等待按键
        if choice != "0":  # 退出时不需要等待
            input("\n按回车键继续...")