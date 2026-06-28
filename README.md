# NCDR 氣候變遷災害風險掃描系統

將 KML 地點批次查詢台灣政府 [NCDR 氣候變遷災害風險圖臺](https://dra.ncdr.nat.gov.tw/Frontend/Tools/ShowMapBoxWMS#)，一次取得淹水與坡地的多維度風險等級，並以互動地圖與 CSV 呈現結果。

---

## 為什麼需要這個系統

當你需要一次評估多個地點的氣候風險，例如：

- **企業選址**：評估幾十個候選廠址或門市，了解各地點的淹水與坡地風險
- **不動產盡職調查**：在買賣或租賃前確認標的物的長期氣候風險
- **供應鏈韌性評估**：確認供應商或倉儲地點在氣候變遷下的暴露程度
- **政府／研究單位**：批次分析一批設施（學校、醫院、避難所）的風險分布

手動在 NCDR 官網逐一查詢 50 個地點需要數小時，本系統只需上傳一個 KML 檔案，幾分鐘內自動完成並輸出報表。

---

## 這個系統在做什麼

NCDR 官網提供台灣各地的氣候變遷災害風險資料，但只能手動一個點一個點查詢、每次只能看一種指標、查完也沒有記錄。

本系統解決以下問題：

| 問題 | 本系統解法 |
|------|-----------|
| 需要一次評估大量地點 | 上傳 KML，自動批次查詢所有地點 |
| 查完沒有紀錄 | 結果自動存成 CSV 報表與互動地圖 |
| 每次只能看一種指標 | 同時回傳 7 個風險維度 |
| 介面複雜、需要 GIS 知識 | 只需準備 KML 或在地圖上點擊即可 |

> 核心技術：直接呼叫 NCDR 的 WMS API（`dwgis1.ncdr.nat.gov.tw`），不是截圖或爬蟲，資料來源與官網完全一致。

---

## 功能

- **批次分析**：上傳 `.kml` 後一鍵查詢所有地點
- **手動標記**：在地圖上點擊新增地點並命名，儲存為 KML 後分析
- **快速查詢**：點擊地圖任意位置，直接查詢該點的所有風險指標
- **地址搜尋**：地圖查詢頁支援中文地址搜尋（Photon / Nominatim）
- **儀表板地圖**：所有分析過的地點在儀表板上一覽無遺
- **CSV 報表**：可下載完整分析結果
- **氣候情境選擇**：支援 1.5°C / 2°C / 4°C 三種全球暖化情境

---

## 風險維度說明

每次查詢回傳以下 7 個指標，情境對應 IPCC AR6 全球暖化程度（GWL）：

| 指標 | 說明 |
|------|------|
| 淹水風險 | 綜合危害度、脆弱度、暴露度的整體風險 |
| 淹水危害度 | 極端降雨造成的積水深度與範圍 |
| 淹水脆弱度 | 該區人口對淹水災害的承受能力 |
| 淹水危害脆弱度 | 危害度與脆弱度的複合指標 |
| 淹水暴露度 | 洪水範圍內的人口密度 |
| 坡地危害度 | 山崩、土石流等坡地災害危害程度 |
| 坡地危害脆弱度 | 坡地危害與脆弱度的複合指標 |

風險等級分為第一至第五級，等級越高代表風險越高。

---

## 專案結構

```
ncdr-risk-scanner/
├── docker-compose.yml
├── README.md
├── worker/               ← 背景工作容器（Python + requests）
│   ├── main.py           ← 監聽工作佇列，呼叫 NCDR WMS API
│   ├── test.kml          ← 預設測試 KML（含 3 個地點）
│   ├── requirements.txt
│   └── Dockerfile
└── web/                  ← 網頁容器（Flask + Leaflet + Jinja2）
    ├── app.py            ← API 路由與頁面
    ├── requirements.txt
    ├── Dockerfile
    ├── static/
    │   └── css/
    └── templates/
        ├── base.html        ← 共用版型與 nav
        ├── index.html       ← 儀表板（KML 管理、分析記錄、地圖總覽）
        ├── map_query.html   ← 地圖查詢（手動標記 / 快速查詢）
        └── results.html     ← 分析結果（風險表格 + 互動地圖）
```

---

## 資料目錄

三個服務共用 `/var/opt/ncdr-risk-scanner/`，容器啟動時自動建立：

```
/var/opt/ncdr-risk-scanner/
├── kmls/       ← 使用者上傳或儲存的 KML 檔案
├── points/     ← 快速查詢的暫存 KML（不顯示在列表）
├── results/    ← 每次分析結果（results.csv + map.html）
└── jobs/       ← 工作佇列 JSON
```

---

## 快速開始

### 需求

- Docker + Docker Compose v2（`docker compose`）

### 啟動

```bash
git clone https://github.com/t33287720/ncdr-risk-scanner.git
cd ncdr-risk-scanner
docker compose up --build -d
```

瀏覽器開啟 `http://localhost:8082`。

若透過 nginx 反向代理，可在 `/ncdr/` 路徑存取：

```nginx
location = /ncdr { return 301 /ncdr/; }
location ^~ /ncdr/ {
    proxy_pass         http://127.0.0.1:8082/;
    proxy_http_version 1.1;
    proxy_set_header   Host $host;
    proxy_set_header   X-Real-IP $remote_addr;
    proxy_read_timeout 300s;
}
```

### 更新程式碼

由於使用 volume 掛載原始碼，修改 `web/` 下的檔案會立即生效（Flask debug 模式）。修改 `worker/` 下的檔案後執行：

```bash
docker compose restart worker
```

---

## 資料來源

- 風險資料：[國家災害防救科技中心 NCDR](https://www.ncdr.nat.gov.tw/)，氣候變遷災害風險圖臺（2025 版，IPCC AR6 GWL 情境）
- 底圖：[OpenStreetMap](https://www.openstreetmap.org/) contributors
- 地址搜尋：[Photon by Komoot](https://github.com/komoot/photon)（開源，無需 API key）

---

## 風險等級色碼

| 等級 | 色碼 |
|------|------|
| 第五級 | `#9F0000` 深紅 |
| 第四級 | `#CA3B00` 橘紅 |
| 第三級 | `#CA7D1D` 橘黃 |
| 第二級 | `#CAB453` 黃 |
| 第一級 | `#CACABA` 灰白 |
