# IBM Quantum 六爻起卦网站

一个量子计算机风格的六爻起卦网页。前端可以部署到 GitHub Pages，本地后端负责调用 IBM Quantum/Qiskit 真机任务。

## 本地运行

```bash
/opt/anaconda3/envs/qiskit/bin/python app.py
```

打开：

```text
http://127.0.0.1:8765
```

## 说明

- 结果区只显示初爻到上爻六条结果。
- 状态栏显示等待状态、量子机和 Job ID。
- IBM Quantum API key 不在仓库里；后端会读取本机已保存的 Qiskit Runtime 账号。
- GitHub Pages 只能托管静态网页，不能直接运行 Qiskit/Python 后端。
