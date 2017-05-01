import re
import csv
import math
import sklearn.cluster
import scipy.sparse
import scipy.sparse.linalg

#总词数计数
word_count = {}

#每个词出现过的文章数
word_dockerfile_count = {}

word_idf = {}

word_bag = {}

#每份dockerfile内每个单词的计数
total_dockerfile_word_list = []

#每份dockerfile总词数
total_dockerfile_word_count = []

#暂存dockerfile内容, 最后分类完后用
dockerfile_id_list = []
dockerfile_name_list = []
dockerfile_content_list = []

word_pattern = re.compile(r"(\S+?)\s")

with open('dockerfile.csv', newline='') as csvfile:
    spamreader = csv.reader(line for line in csvfile)
    for row in spamreader:
        word_list = word_pattern.findall(row[2].replace('\n', ' '))
        dockerfile_word_count = {}
        w_c = 0
        if len(word_list) > 0:
            for word in word_list:
                w_c += 1
                #填写初始word_bag, 后续再去掉只出现一次的word
                if word in word_count:
                    word_count[word] += 1
                else:
                    word_count[word] = 1

                #填写每个词到该dockerfile的word_count list里
                if word in dockerfile_word_count:
                    dockerfile_word_count[word] += 1
                else:
                    dockerfile_word_count[word] = 1

            #对每个词出现过的文章数计数, 用以计算idf
            for word in dockerfile_word_count:
                if word in word_dockerfile_count:
                    word_dockerfile_count[word] += 1
                else:
                    word_dockerfile_count[word] = 1

        dockerfile_id_list.append(row[0])
        dockerfile_name_list.append(row[1])
        dockerfile_content_list.append(row[2])
        total_dockerfile_word_count.append(w_c)
        total_dockerfile_word_list.append(dockerfile_word_count.copy())


#读取和处理csv完毕
print("read csv finish")

dockerfile_count = len(dockerfile_id_list)
#只把出现超过一次的词存入word_bag
#但是在用外部库做聚类计算的时候, 距离函数不是自己写的, 没办法处理, 所以还是把所有词都存入word_bag
count = 0
for word in word_count:
    #if word_count[word] > 1:
    word_bag[word] = count
    count += 1
    word_idf[word] = math.log(dockerfile_count / (word_dockerfile_count[word] + 1.0))

#计算词的idf值


print("build word bag finish")

dockerfile_word_lil_matrix = scipy.sparse.lil_matrix((dockerfile_count, len(word_bag)), dtype='float')

count = 0
for d_w_c in total_dockerfile_word_list:
    for word in d_w_c:
        if word in word_bag:
            dockerfile_word_lil_matrix[count, word_bag[word]] = (d_w_c[word]/total_dockerfile_word_count[count])*word_idf[word]
    count += 1

dockerfile_word_csr_matrix = dockerfile_word_lil_matrix.tocsr()
print("build dockerfile-word lil_matrix finish")

res = sklearn.cluster.DBSCAN(eps=0.3, min_samples=2).fit(dockerfile_word_csr_matrix)
#res = sklearn.cluster.KMeans(n_clusters=500).fit(dockerfile_word_csr_matrix)

print("cluster finish")

# 返回的res.labels_是一个打完label的数组, 编号为0, 1, ... , x (离群太远的噪声点标为-1)
#print(res.labels_)

with open('result.csv', 'w', newline='') as csvfile_res:
    spamwriter = csv.writer(csvfile_res)
    for i in range(dockerfile_count):
        spamwriter.writerow([dockerfile_id_list[i], dockerfile_name_list[i], res.labels_[i], dockerfile_content_list[i]])

print("write result into csv file finish")

