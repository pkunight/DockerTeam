import pymysql
import csv
import re

maintainer_pattern = re.compile(r"(MAINTAINER|#)[^\n]*?\n")

db_ip = "112.74.190.220"
dockerteam_db = pymysql.connect(db_ip, "dockerteam", "docker", "dockerteam", use_unicode=True,
                                            charset="utf8")
dockerteam_cursor = dockerteam_db.cursor()

dockerteam_cursor.execute("SELECT id, dockerfile_name, dockerfile_content from dockerteam.dockerfile")

with open('dockerfile.csv', 'w', newline='') as csvfile:
    spamwriter = csv.writer(csvfile)
    for row in dockerteam_cursor.fetchall():
        spamwriter.writerow([row[0], row[1].replace('\0', ''), re.sub(maintainer_pattern, '', row[2].replace('\0', ''))])

dockerteam_cursor.close()
dockerteam_db.close()
