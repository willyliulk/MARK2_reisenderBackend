var ctxPos = document.getElementById("plotPos").getContext("2d");
var ctxVel = document.getElementById("plotVel").getContext("2d");
var imgCam1Frame = document.getElementById("cam1_frame");
var wsAddrInput = document.getElementById("wsAddrInput");
var motorPosDisplay = document.getElementById("motorPosDisplay");
var motorVelDisplay = document.getElementById("motorVelDisplay");


class App {
    constructor(ctxPos, ctxVel, imgCam1Frame, wsAddr) {
        this.wsAddr = wsAddr;
        this.wsPort = 8800;

        // 資料線樣式
        this.dataPos = {
            labels: [],
            datasets: [{
                label: 'Real-time data',
                borderColor: 'rgb(75, 192, 192)',
                data: [],
                fill: false,
            }],
        }
        this.dataVel = {
            labels: [],
            datasets: [{
                label: 'Real-time data',
                borderColor: 'rgb(75, 192, 192)',
                data: [],
                fill: false,
            }],
        }

        // 圖表樣式
        this.configPos = {
            type: 'line',
            data: this.dataPos,
            options: {
                responsive: true,
                animation: {
                    duration: 0,
                    easing: 'linear'
                },
                scales: {
                    x: {
                        type: 'linear',
                        position: 'bottom',
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Value'
                        },
                        suggestedMin: 0,
                        suggestedMax: 100
                    }
                }
            }
        }
        this.configVel = {
            type: 'line',
            data: this.dataVel,
            options: {
                responsive: true,
                animation: {
                    duration: 0,
                    easing: 'linear'
                },
                scales: {
                    x: {
                        type: 'linear',
                        position: 'bottom',
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Value'
                        },
                        suggestedMin: 0,
                        suggestedMax: 100
                    }
                }
            }
        }

        // 圖表更新參數
        this.dataPointsLinit = 300;
        this.dateUpdateRate = 100; // ms

        // 定義圖表本體
        this.chartPos = new Chart(ctxPos, this.configPos);
        this.chartVel = new Chart(ctxVel, this.configVel);

        // 定義馬達數據變數
        this.motorPos = 0;
        this.motorVel = 0;

        //定義websocket與綁定資料接收函式
        this.wsMotor = new WebSocket(`ws://${this.wsAddr}:${this.wsPort}/ws/motor/data`);
        this.wsMotor.onmessage = this.callbackWsMotorData;

        // 定義自動更新圖表定時器
        this.chartUpdateHadle = setInterval(this.updateChart, this.dateUpdateRate);
        
        // 定義相機串流框
        this.imgCam1Frame = imgCam1Frame;
        this.weCam1 = new WebSocket(`ws://${this.wsAddr}:${this.wsPort}/ws/cam/1`);
        this.weCam1.onmessage = this.updateCamera_1;
    }

    callbackWsMotorData = (event) => {
        var motorData = JSON.parse(event.data);
        this.motorPos = motorData.pos;
        this.motorVel = motorData.vel;

        this.updateMotorDatas();
    }

    addData = (dataToAdd, newValue) => {
        var curTime = new Date().getTime();
        
        if(dataToAdd.labels.length > this.dataPointsLinit){
            dataToAdd.labels.shift();
            dataToAdd.datasets[0].data.shift();
        }
        
        dataToAdd.labels.push(curTime);
        dataToAdd.datasets[0].data.push(newValue);
    }

    updateMotorDatas = () => {
        this.addData(this.dataPos, this.motorPos);
        this.addData(this.dataVel, this.motorVel);
    }

    updateChart = () => {
        this.chartPos.update();
        this.chartVel.update();
        motorVelDisplay.value = this.motorVel;
        motorPosDisplay.value = this.motorPos;
    }

    stopUpdateChart = () => {
        clearInterval(this.chartUpdateHadle);
    }

    updateCamera_1 = (event) => {
        this.imgCam1Frame.src = `data:image/jpeg;base64,${event.data}`
    }
}



var app = new App(ctxPos, ctxVel, imgCam1Frame, 'localhost');

function reloadWs() {
    clearInterval(app.chartUpdateHadle);
    app.chartPos.destroy();
    app.chartVel.destroy();
    app = new App(ctxPos, ctxVel, imgCam1Frame, wsAddrInput.value)
}