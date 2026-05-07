# IBM Quantum 六爻起卦网站

一个量子计算机风格的六爻起卦网页。GitHub Pages 负责网页界面，Python 后端负责调用 IBM Quantum/Qiskit 真机任务。

如果希望电脑关机后仍然能用，需要把 Python 后端部署到云服务器。任何设备打开网页时，流程是：

```text
手机/电脑浏览器 -> GitHub Pages 前端 -> 云端 Python 后端 -> IBM Quantum 真机
```

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
- IBM Quantum API key 不在仓库里；本地后端会读取本机已保存的 Qiskit Runtime 账号。
- 部署到云端时，把 `IBM_QUANTUM_API_KEY` 和 `IBM_QUANTUM_INSTANCE` 放到服务器环境变量里。
- GitHub Pages 只能托管静态网页，不能直接运行 Qiskit/Python 后端；真机起卦必须有 Python 后端在运行。

## 云端部署

1. 把仓库部署到 Render/Railway/Fly.io/Cloud Run 这类能运行 Python 的平台。仓库已经包含 `render.yaml`、`Procfile`、`requirements.txt`。
2. Start command 使用：

```bash
python app.py --host 0.0.0.0 --port $PORT
```

3. 在平台环境变量里设置：

```text
IBM_QUANTUM_API_KEY=你的 IBM Quantum API key
IBM_QUANTUM_INSTANCE=你的 IBM Quantum instance CRN
IBM_QUANTUM_CHANNEL=ibm_quantum_platform
```

4. 如果前端继续用 GitHub Pages，部署后把 `static/config.js` 里的 `window.LIUYAO_API_BASE` 改成你的后端 URL。
5. 重新 push 到 GitHub Pages 后，手机或任何电脑打开网页都可以起卦；不再依赖这台 MacBook 开机。

不要把真实 API key 写进代码或提交到 GitHub。
