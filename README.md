此軟體包由黎聲科技製作，並受版權保護。
若有任何問題請聯絡email：sales@reisendertech.com

該軟體包使用uv python 包管理器管理
請[安裝uv](https://docs.astral.sh/uv/getting-started/installation/)後使用下方指令完成環境安裝
``` bash
uv sync
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

請勿修改此文件