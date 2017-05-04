import requests
import re
import pymysql
import uuid


class CopyEntity:
    def __init__(self, command, url, content):
        self.command = command
        self.url = url
        self.content = content

p_name = re.compile(r".+/(.+?)/(.+?)/")

p_github_url = re.compile(r"<a href=\"https://github.com/(.+?)\"")

p_dockerfile_div = re.compile(r"<div class=\"hljs\".+?>([\s\S]+?)</div>")
p_file_content = re.compile(r"<span.+?>|</span>")

run_command_pattern = re.compile(r"RUN[\S\s]+?[^\\]\n")
copy_command_pattern = re.compile(r"COPY[\s\S]+?\n|ADD[\s\S]+?\n")
copy_filename_pattern = re.compile(r"(COPY|ADD)\s(.+?)\s(.+?)\n")

file_table_pattern = re.compile(r"<table class=\".+?js-file-line-container.+?>([\s\S]+?)</table>")
files_table_list_pattern = re.compile(r"<table class=\"files.+?>([\s\S]+?)</table>")
a_link_pattern = re.compile(r"<td class=\"content\">[\s\S]*?<span.+?>[\s\S]*?<a href=\"(.+?)\"")
file_content_pattern = re.compile(r"<td id=\"LC.+?>([\s\S]+?)</td>")


def getName(html_url):
    name = p_name.findall(html_url)
    if len(name) > 0:
        return name[0][0] + "/" + name[0][1]
    else:
        return ""


def getDockerfileFromHtml(html_url):
    _url = html_url+"~/dockerfile/"
    #print(_url)

    req = requests.get(url=_url)

    res_github_url = p_github_url.findall(req.text)
    if len(res_github_url) > 0:
        res_github_url = res_github_url[0]
    else:
        res_github_url = ""

    res_div = p_dockerfile_div.findall(req.text, re.M)

    if len(res_div) > 0:
        res_content = re.sub(p_file_content, "", res_div[0])
        res_content = res_content.replace("\\", "\\\\")
        res_content = res_content.replace("\"","\\\"")
        if len(res_content) == 0:
            res_content = ""
    else:
        res_content = ""

    return res_content, res_github_url


def getRunCommandList(dockerfile_content):
    run_command_list = run_command_pattern.findall(dockerfile_content)
    #print("run_command_list:", run_command_list)
    return run_command_list

g_f_c_list = []


def recurseSearchGithub(github_url_with_filename, c):
    global g_f_c_list
    try:
        #print("recurseSearchGithub url:", github_url_with_filename)
        req = requests.get(url=github_url_with_filename)
        files_list = files_table_list_pattern.findall(req.text)
        file_table = file_table_pattern.findall(req.text)
        # print("files_list:", files_list)
        # print("file_table:", file_table)
        if len(files_list) > 0:
            # print("files list")
            a_link_list = a_link_pattern.findall(files_list[0])
            for a_link in a_link_list:
                a_link = "https://github.com" + a_link
                if a_link != github_url_with_filename:
                    recurseSearchGithub(a_link, c)
        elif len(file_table) > 0:
            # print("file table")
            copy_file_content_entity = CopyEntity(c.rstrip('\n'), github_url_with_filename, "")
            file_content_list = file_content_pattern.findall(file_table[0])
            file_content = ""
            for f_c in file_content_list:
                file_content += f_c + "\n"
            copy_file_content_entity.content = re.sub(p_file_content, "", file_content)
            g_f_c_list.append(copy_file_content_entity)
        else:
            print("No github content, url=", github_url_with_filename)
    except Exception as e:
        print("recurseSearchGithub Exception:", e, "url=", github_url_with_filename)


def getCopyFileList(dockerfile_content, github_url):
    global g_f_c_list
    _url = "https://github.com/" + github_url
    copy_list = copy_command_pattern.findall(dockerfile_content, re.M)
    #print("copy_list:", copy_list)
    for c in copy_list:
        filename = copy_filename_pattern.findall(c)
        if len(filename) > 0:
            # print("filename:", filename)
            from_filename = filename[0][1]
            from_filename = from_filename.rstrip('/')
            # print("from_filename:", from_filename)

        if from_filename == ".":
            #直接递归搜索该github链接下的所有文件即可
            recurseSearchGithub(_url, c)
        else:
            try:
                # 先获取需要的文件/文件夹的url,再进入递归搜索过程
                req = requests.get(url=_url)
                # print("github_url:", github_url, "_url:", _url)
                files_list = files_table_list_pattern.findall(req.text)
                if len(files_list) > 0:
                    # print("files_list:", files_list[0])
                    a_link_list = a_link_pattern.findall(files_list[0])
                    # print("a_link_list:", a_link_list)
                    search_link_pattern = re.compile(r"/" + github_url + "/.+?/.+?/" + from_filename + "$")
                    for a_link in a_link_list:
                        # print("a_link:", a_link)
                        search_link = search_link_pattern.findall(a_link)
                        # print("search_link:", search_link)
                        if len(search_link) > 0:
                            recurseSearchGithub("https://github.com/" + search_link[0], c)
            except Exception as e:
                print("getCopyFileList Exception:", e, "url=", _url)

db_ip = "[ip]"

test_db = pymysql.connect(db_ip,"dockerteam","docker","test", use_unicode=True, charset="utf8")
test_cursor = test_db.cursor()
dockerteam_db = pymysql.connect(db_ip, "dockerteam", "docker", "dockerteam", use_unicode=True, charset="utf8")
dockerteam_cursor = dockerteam_db.cursor()

count = 288888
test_cursor.execute("SELECT url from test.images limit "+str(count)+", 200000")

for row in test_cursor.fetchall():
    count = count + 1
    print(count)
    dockerhub_url = row[0]
    dockerfile_name = getName(dockerhub_url)
    print(dockerfile_name)

    dockerfile_content, github_url = getDockerfileFromHtml(dockerhub_url)
    #print(dockerfile_content)
    #print(github_url)

    #每隔一定次数重连一次数据库
    reconnect_count = 1
    if len(dockerfile_content) > 0:
        dockerfile_uuid = uuid.uuid1()
        try:
            if reconnect_count == 0:
                dockerteam_db = pymysql.connect(db_ip, "dockerteam", "docker", "dockerteam", use_unicode=True,
                                            charset="utf8")
                dockerteam_cursor = dockerteam_db.cursor()
                reconnect_count += 1

            #Insert dockerfile content
            sql = "INSERT INTO dockerfile(uuid, dockerhub_url, dockerfile_name, github_url, dockerfile_content) VALUES(\"%s\", \" %s\", \" %s\", \" %s\", \"%s\")" % (dockerfile_uuid, dockerhub_url, dockerfile_name, github_url, dockerfile_content)
            effect_row = dockerteam_cursor.execute(sql)

            dockerteam_db.commit()

            # if effect_row > 0:
            #     print("Inserted dockerfile into database")
            #     #print("dockerfile_content:",dockerfile_content)
            #     # Insert run command
            #     run_command_list = getRunCommandList(dockerfile_content)
            #     for r_c in run_command_list:
            #         sql = "INSERT INTO run_command(dockerfile_uuid, run_command) VALUES(\"%s\", \"%s\")" % (dockerfile_uuid, r_c)
            #         effect_row2 = dockerteam_cursor.execute(sql)
            #
            #     # Insert copy file content
            #     g_f_c_list = []
            #     getCopyFileList(dockerfile_content, github_url)
            #     for f_c_e in g_f_c_list:
            #         #print(f_c_e.command)
            #         #print(f_c_e.url)
            #         #print(f_c_e.content)
            #         sql = "INSERT INTO githubfile(dockerfile_uuid, copy_command, url, file_content) VALUES(\"%s\", \"%s\", \"%s\", \"%s\")" % (dockerfile_uuid, f_c_e.command, f_c_e.url, f_c_e.content)
            #         effect_row3 = dockerteam_cursor.execute(sql)
            #     dockerteam_db.commit()

            if reconnect_count == 10:
                dockerteam_db.close()
                reconnect_count = 0

        except pymysql.InternalError as e:
            print("pymysql.InternalError Exception:", e)
        except Exception as e:
            print("Exception:", e)
    else:
        print("no dockerfile content, ignore")

test_db.close()
dockerteam_db.close()
