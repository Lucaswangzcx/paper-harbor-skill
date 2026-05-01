# Paper Harbor Skill

Paper Harbor 是一个 Codex skill，用来从 ScienceDirect 和知网整理文献信息，并把筛选后的条目保存到 Zotero。它现在只做元数据整理和 Zotero 入库，不下载 PDF，也不点全文下载按钮。
ScienceDirect 和知网都走同一条流程：打开默认浏览器里的已登录站点、先让用户登录 EasyScholar、先在站点里检索关键词、在结果页看 IF/分区标签、创建输出目录、收集候选元数据、筛掉不符合影响因子要求的条目，再逐条写入 Zotero。区别只在网页控件和字段解析。

## 它做什么

- 按关键词、年份、影响因子和目标入库篇数整理文献
- 保存题名、作者、期刊、年份、DOI、官方地址、影响因子、来源说明
- 先写出候选清单，再逐条保存到 Zotero
- 支持把条目保存到指定 Zotero collection，例如 `science direct`
- ScienceDirect / 知网页面上如果 EasyScholar 已经显示 `IF 9.8` 这类标签，会直接读取这个 IF，并按用户的影响因子要求筛选
- 如果 Zotero 入库失败，也会留下候选表、地址表和待处理原因

## 不做什么

- 不下载 PDF、HTML、XML 全文
- 不点击 `View PDF`、`Download PDF`、`Download selected articles`、`Download full issue`
- 不绕过登录、验证码、付费墙、机构权限、异常访问提示
- 不使用盗版镜像或共享账号
- 不并发处理，一次只保存一条

## 第一次使用

先装好这些东西：

1. Zotero Desktop
2. 当前浏览器里的 Zotero Connector
3. 当前浏览器里的 EasyScholar
4. Zotero 里建好对应 collection，例如 `science direct`、`中国知网`
5. 如果要看影响因子，先在同一个默认浏览器里登录 EasyScholar，并刷新结果页，确保能看到 `IF 9.8` 这类标签

可以运行这个辅助脚本打开官方页面：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\open_zotero_setup.ps1
```

检查 Zotero 是否可用：

```powershell
python .\scripts\zotero_bridge.py doctor
```

`doctor` 里应该能看到 Zotero 本地接口、Zotero 数据目录，以及当前选中的 collection/targets。

## 浏览器端口

- ScienceDirect: `9225`
- 中国知网/CNKI: `9226`

打开对应默认浏览器后，用户自己登录网站，再登录 EasyScholar。Paper Harbor 不输入账号密码，也不处理验证码。

## 提示词模板

```text
Use skill paper-harbor 帮我在“网站名”整理“关键词”的“时间限制”文献，“影响因子限制”，“篇数限制”，保存到 Zotero 的“Zotero目录名”并输出到“目录”
```

这里的“10篇/25篇”表示尽量保存这么多篇**符合条件**的 Zotero 元数据，不是只检查前 10 条搜索结果。不符合影响因子、IF 待核验、验证码/权限不清楚的条目会写进待处理清单，不占用目标篇数。

例子：

```text
Use skill paper-harbor 帮我在“ScienceDirect”整理“solid electrolyte interphase”的“2021-2026”文献，“影响因子大于5”，“25篇”，保存到 Zotero 的“science direct”并输出到“.\runs\sei”
```

## ScienceDirect 实跑命令

```powershell
python .\scripts\sciencedirect_drission_run.py --port 9225 --query "solid electrolyte interphase" --year-from 2021 --year-to 2026 --if-min 5 --limit 25 --zotero-collection "science direct" --out ".\runs\sei-test"
```

运行时会先保存候选表，再把符合条件的条目保存到 Zotero 指定 collection。EasyScholar 没显示 IF 的条目会标记为 `IF待核验`，不会被当成满足影响因子条件。
如果你要求 `影响因子大于 5`，但页面还没显示 EasyScholar IF 标签，脚本会先停在候选层，提醒你先在默认浏览器里登录 EasyScholar 再重新跑。

## 输出目录

每次运行会生成这些文件：

```text
00_先看我_文件说明.txt
README_先看我.md
文献整理报告.html
文章地址总表.csv
候选文献总表.csv
高优先级文献.csv
中优先级文献.csv
低优先级文献.csv
已入库Zotero文献清单.csv
待处理文献清单.csv
检索计划.md
内部数据_一般不用打开/
```

## 开源说明

仓库不应该包含账号、Cookie、PDF、Zotero 数据库、运行结果或机构访问凭证。`runs/`、`内部数据_一般不用打开/`、`.sqlite`、`.pdf`、`.csv` 等运行产物默认不提交。
