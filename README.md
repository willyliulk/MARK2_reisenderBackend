該軟體包使用uv python 包管理器管理
請[安裝uv](https://docs.astral.sh/uv/getting-started/installation/)後使用下方指令完成環境安裝
``` bash
uv sync
```

文件中附上openapi.json，可以作為不使用模擬伺服器時的參考

執行程式請使用以下指令\
開啟一個終端執行，啟動模擬器
系統於winidows上開發，ubuntu系統也可使用
```lang=bash
cd MARK2_reisenderBackend
source .venv/bin/activate # linux
uv run .\mechineSimulator\testPlace3.py 
```
開啟第二個終端執行，啟動後端API伺服器，會運行在8800端口上
```lang=bash
cd MARK2_reisenderBackend
source .venv/bin/activate # linux
uv run ./app.py 
```


## websocket 設計
目前提供三個webcoket端點 \
簡單說明一下資料表示法：\
`{"IDEL", "RUNNING", "ERROR"}` \
代表結果會是"IDEL", "RUNNING", "ERROR" 其中一個的string \

`["shot", "EMG"]` \
代表結果會是一個array 可能有這兩個string，這主要用在mechine 的機上按鈕結果 \
如果只有按下shot，結果會是 ["shot"] \
如果都按下，結果會是 ["shot", "EMG"] \
如果沒有按下，結果會是 [] 空陣列 \

* /v2/ws/motor/{id}/data
```
{
    id          :int,
    pos         :float,
    vel         :float,
    state       :{"IDEL", "RUNNING", "ERROR"},
    proximitys  :[bool, bool],
    is_home     :bool,
}
```

* /v2/ws/cam/{id}
```
base64 編碼圖像
可參考 /html/testPage.html
有其他序列化需求可再討論
```

* /v2/ws/mechine
```
{
    emergency   :bool,
    reason      :string,
    state       :{"IDEL", "SHOTTING", "AI_PROC", "ERROR"},
    colorLight  :{"r", "g", "y"},
    btn_on      :["shot", "EMG"]
}
```

此軟體包由黎聲科技製作，並受版權保護。
若有任何問題請聯絡email：sales@reisendertech.com
請勿修改此文件