import requests
import re
import pymysql
import uuid


class CopyEntity:
    def __init__(self, command, file_content):
        self.command = command
        self.file_content = file_content

p_name = re.compile(r".+/(.+?)/(.+?)/")

p_github_url = re.compile(r"github.com/(.+?)\"")

p_dockerfile_div = re.compile(r"<div class=\"hljs\".+?>([\s\S]+?)</div>")
p_dockerfile_content = re.compile(r"<span.+?>|</span>")

run_command_pattern = re.compile(r"RUN[\S\s]+?[^\\]\n")
copy_command_pattern = re.compile(r"COPY[\s\S]+?\n|ADD[\s\S]+?\n")
copy_filename_pattern = re.compile(r"(COPY|ADD)\s(.+?)\s(.+?)\n")

file_table_pattern = re.compile(r"<table class=\"highlight.+?>([\s\S]+?)</table>")
files_table_list_pattern = re.compile(r"<table class=\"files.+?>([\s\S]+?)</table>")
a_link_pattern = re.compile(r"<a href=\"(.+)\"")

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
        res_content = re.subn(p_dockerfile_content, "", res_div[0])
        res_content = res_content[0].replace("\"","\\\"")
        if len(res_content) == 0:
            res_content = ""
    else:
        res_content = ""

    return res_content, res_github_url

def getRunCommandList(dockerfile_content):
    run_command_list = run_command_pattern.findall(dockerfile_content)
    #print("run_command_list:", run_command_list)
    return run_command_list

def recurseSearchGithub(github_url_with_filename, c):
    list = []
    req = requests.get(url=github_url_with_filename)
    files_list = files_table_list_pattern.findall(req.text)
    file_table = file_table_pattern.findall(req.text)
    if len(files_list) > 0:
        print("files list")
        a_link_list = a_link_pattern.findall(files_list[0][0])
        for a_link in a_link_list:
            recurseSearchGithub(a_link, c)
    elif len(file_table) > 0:
        print("file table")
        copy_file_content_entity = CopyEntity(c, "")

    else:
        print("No github content")

    return list

def getCopyFileList(dockerfile_content, github_url):
    _url = "https://github.com/" + github_url
    copy_list = copy_command_pattern.findall(dockerfile_content, re.M)
    #print("copy_list:", copy_list)
    copy_file_content_list = []
    for c in copy_list:
        filename = copy_filename_pattern.findall(c)
        #print("filename:", filename)
        from_filename = filename[0][1]
        to_filename = filename[0][2]
        #print(from_filename, to_filename)

        if from_filename == ".":
            #直接递归搜索该github链接下的所有文件即可
            recurseSearchGithub(_url, c)
        else:
            #先获取需要的文件/文件夹的url,再进入递归搜索过程
            req = requests.get(url=_url)
            a_link_list = a_link_pattern.findall(req.text)
            search_link_pattern = re.compile(r"https://github.com"+github_url+".*"+from_filename)
            for a_link in a_link_list[0]:
                search_link = search_link_pattern.findall(a_link_list)[0][0]
                if len(search_link) > 0:
                    recurseSearchGithub(search_link, c)

    return copy_list, copy_file_content_list


test_db = pymysql.connect("[ip]","dockerteam","docker","test")
dockerteam_db = pymysql.connect("[ip]","dockerteam","docker","dockerteam")

test_cursor = test_db.cursor()
dockerteam_cursor = dockerteam_db.cursor()

test_cursor.execute("SELECT url from test.images where id = 403964 limit 0,-1")
count = 0
for row in test_cursor.fetchall():
    count = count + 1
    print(count)
    dockerhub_url = row[0]
    dockerfile_name = getName(dockerhub_url)
    print(dockerfile_name)

    dockerfile_content, github_url = getDockerfileFromHtml(dockerhub_url)
    #print(dockerfile_content)
    #print(github_url)

    if dockerfile_content != "":
        dockerfile_uuid = uuid.uuid1()
        try:
            #Insert dockerfile content
            effect_row = dockerteam_cursor.execute("INSERT INTO dockerfile(uuid, dockerhub_url, dockerfile_name, github_url, dockerfile_content) VALUES(\"%s\", \" %s\", \" %s\", \" %s\", \"%s\")" % (dockerfile_uuid, dockerhub_url, dockerfile_name, github_url, dockerfile_content))
            if effect_row > 0:
                print("Insert dockerfile into database")

                # Insert run command
                run_command_list = getRunCommandList(dockerfile_content)
                for run_command_content in run_command_list:
                    effect_row = dockerteam_cursor.execute("INSERT INTO run_command(dockerfile_uuid, run_command) VALUES(\"%s\", \"%s\")" % (dockerfile_uuid, run_command_content))

                # Insert copy file content
                copy_file_content_list = getCopyFileList(dockerfile_content, github_url)

                dockerteam_db.commit()
            else:
                print("Insert fail without exception")
        except Exception as e:
            print("Exception:", e)
    else:
        print("no dockerfile content, ignore")

test_db.close()
dockerteam_db.commit()
dockerteam_db.close()
