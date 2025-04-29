
let wsAddrInput = document.getElementById('wsAddrInput');
let wsDisplayer = document.getElementById('wsDisplayer');

let motorPosField = document.getElementById('motorPosField');
let motorVelField = document.getElementById('motorVelField');
let motorMoveIncField = document.getElementById('motorMoveIncField');
let motorMoveAbsField = document.getElementById('motorMoveAbsField');

let motorSPlist = document.getElementById('motorSPlist');

let cam1_Img = document.getElementById('cam1_Img');
let cam2_Img = document.getElementById('cam2_Img');

let splide1 = new Splide( '#cam1_slide' ).mount();
let splide2 = new Splide( '#cam2_slide' ).mount();
let cam1_slideBox = document.getElementById('cam1_slideBox');
let cam2_slideBox = document.getElementById('cam2_slideBox');

let resultDisplay = document.getElementById('resultDisplay');
let resultImg = document.getElementById('resultImg');
let resultCardContainer = document.getElementById('resultCardContainer');
let resultCard_Slide_List = [];

// var wsAddr='localhost';
// var wsPort='8800';
const url = new URL(window.location.href);
var wsAddrPort = url.hostname;
if (url.port !== null){
    wsAddrPort += ':' + url.port;
}
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';


var wsMotorData = new WebSocket(`${protocol}//${wsAddrPort}/ws/motor/data`);
var wsCam1      = new WebSocket(`${protocol}//${wsAddrPort}/ws/cam/1`);
var wsCam2      = new WebSocket(`${protocol}//${wsAddrPort}/ws/cam/2`);


var motorPos=0, motorVel=0;

let lastCallTime = 0;
const minInterval = 2000; // 2 seconds in milliseconds

function callbackWsMotorData(event) {
    var motorData = JSON.parse(event.data);
    motorPos = motorData.pos;
    motorVel = motorData.vel;
    btnStopState = motorData.btnShot;
    
    if(btnStopState == 1){
        const currentTime = Date.now();
        if (currentTime - lastCallTime >= minInterval) {
            lastCallTime = currentTime;
            setTimeout(click_camShotAndPost, 300);
        }
    }

    motorPosField.innerHTML = motorPos;
    motorVelField.innerHTML = motorVel;
}

function callbackWsCamera_1(event) {
    cam1_Img.src = `data:image/webp;base64,${event.data}`
}
function callbackWsCamera_2(event) {
    cam2_Img.src = `data:image/webp;base64,${event.data}`
}
function callbackWsCamera_3(event) {
    cam3_Img.src = `data:image/webp;base64,${event.data}`
}
function callbackWsCamera_4(event) {
    cam4_Img.src = `data:image/webp;base64,${event.data}`
}
async function click_motorStop() {
    await fetch(`/motor/move/stop`);
}

async function click_motorIncMinus() {
    var motorIncValue = "-" + motorMoveIncField.value;
    await fetch(`/motor/move/inc/${motorIncValue}`);
}
async function click_motorIncPlus() {
    var motorIncValue = motorMoveIncField.value;
    await fetch(`/motor/move/inc/${motorIncValue}`);
}

async function click_motorAbs() {
    var motorAbsValue = motorMoveAbsField.value;
    await fetch(`/motor/move/abs/${motorAbsValue}`);
}


async function click_motorMoveSP() {
    var motorSPListItems = motorSPlist.children;
    var listSPvalue = [];
    for (let i = 0; i < motorSPListItems.length; i++) {
        const element = motorSPListItems[i];
        var SPvalue = element.children[0].value;
        listSPvalue.push(SPvalue);
        
        console.log(SPvalue);
    }

    await fetch(`/motor/move/sp`,{
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(listSPvalue)
    });
}

function buildLiElement(preSetValue=1000) {

    const newItem = document.createElement('li');

    const input = document.createElement('input');
    input.type = 'number';
    input.value = `${preSetValue}`;

    const btnUpdate = document.createElement('button');
    btnUpdate.textContent = 'update';
    btnUpdate.setAttribute('onclick', 'click_motorSPupdate(this)');
    btnUpdate.setAttribute('class', 'motorSPupdate');
    const btnRemove = document.createElement('button');
    btnRemove.textContent = '-';
    btnRemove.setAttribute('onclick', 'click_motorSPremove(this)');
    btnRemove.setAttribute('class', 'motorSPremove');

    newItem.appendChild(input);
    newItem.appendChild(btnUpdate);
    newItem.appendChild(btnRemove);

    return newItem;
}

function click_motorSP_add(preSetValue=1000) {
    console.log('add SP');

    motorSPlist.appendChild(buildLiElement(preSetValue));
    motorSPlist.offsetHeight;
}

function click_motorSPupdate(button) {
    var SPfield = button.parentElement.children[0];
    SPfield.value = motorPosField.innerHTML; 
    console.log(motorPosField);
}

function click_motorSPremove(button) {
    button.parentElement.remove();
}

var range = (start, stop, step=1) => {
    const length = Math.ceil((stop - start) / step);
    return Array.from({length}, (_, i) => (i * step) + start);
}


async function click_camShot(){
    var motorSPListItems = motorSPlist.children;
    var listSPvalue = [];
    for (let i = 0; i < motorSPListItems.length; i++) {
        const element = motorSPListItems[i];
        var SPvalue = element.children[0].value;
        listSPvalue.push(SPvalue);
        
        console.log(SPvalue);
    }

    let response = await fetch(`/cam/shot`,{
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(listSPvalue)
    });
    let jsonRes = await response.json();
    console.log(jsonRes);

    console.log("start change slide content");

    splide1.remove( range(0, splide1.length, 1) );
    splide2.remove( range(0, splide2.length, 1) );
    
    for(var i = 0; i < jsonRes['cam1'].length; i++) {
        let tempChind1 = `<li class="splide__slide"><img src="data:image/webp;base64,${jsonRes['cam1'][i]}"></li>`;
        splide1.add( tempChind1 );
        let tempChind2 = `<li class="splide__slide"><img src="data:image/webp;base64,${jsonRes['cam2'][i]}"></li>`;
        splide2.add( tempChind2 );
    }

}

function resultCard_factory(title, probability, type, make, subcatehory, imgPaths){
    var probability_str = '';
    if(probability > 0.12){
        probability_str = "High";
    }else if(probability > 0.08){
        probability_str = "Medium";
    }else{
        probability_str = "Low";
    }

    var type_str = '';
    if(type === "torque_converter"){
        type_str = 'Converter';
    }else if(type === "transmission_case"){
        type_str = 'Transmission';
    }

    return {
        title: title,
        possibility: probability_str,
        type: type_str,
        make: make,
        subcatehory: subcatehory,
        imgPaths: imgPaths
    }
}


function make_one_ResultCard(result_card, card_num){
    console.log("let's make one card   !!!!!!!")
    var imgItems=[];
    result_card.imgPaths.forEach( (imgPath) => {
        imgItems.push(`<img class="splide__slide" src="${imgPath}">`)
    } );
    var cardTemplate = 
`    
    <div id="page_${card_num}" class="pageDiv">
        <section id="splide${card_num}" class="splide" aria-label="Splide Basic HTML Example">
            <div class="splide__track">
                <ul class="splide__list">
                    ${imgItems}
                </ul>
            </div>
        </section>

        <h3 class="itemTitle">
            ${result_card.title}
        </h3>

        <div class="itemDetail content">
            <p class="itemDetail title">Possibility</p> <div class="itemDetail field ${result_card.possibility}"><p>${result_card.possibility}</p></div>
            <p class="itemDetail title">Type</p>        <p class="itemDetail field">${result_card.type}</p>
            <p class="itemDetail title">Make</p>        <p class="itemDetail field">${result_card.make}</p>
            <p class="itemDetail title">Subcatehory</p> <p class="itemDetail field">${result_card.subcatehory}</p>
        </div>
    
`;
    return [cardTemplate, `splide${card_num}`];
}

function renderResultCards(result_card_list){


    resultCard_Slide_List.forEach( (resultCard_Slide) => {
        resultCard_Slide.destroy();

    });
    resultCard_Slide_List.length = 0;

    resultCardContainer.innerHTML = '';
    result_card_list.forEach( (card, index) => {
        let [cardHTML, slideName] = make_one_ResultCard(card, index);

        resultCardContainer.insertAdjacentHTML('beforeend', cardHTML);
        resultCard_Slide_List.push(
            (new Splide( `#${slideName}` )).mount()
        );
    } );
}

async function click_resultButton() {
    resultCardContainer.innerHTML = "<p>辨識中</p>"
    
    var resultAI_raw = await fetch(`/result/upload`);
    var resultAI_json = await resultAI_raw.json();
    var resultAIs = resultAI_json['result'];
    var resultAI_savePlace = resultAI_json['savePlace'];
    
    var result_card_list = Array(resultAIs.length);
    await Promise.all(resultAIs.map(async (ai_result, ai_result_index) => { 

        console.log(`probability_${ai_result_index}:${ai_result.probability}`);
        var imgPathURL = `/photo/${ai_result.part}/${ai_result.directory}`;

        var imgPath_raw = await fetch(imgPathURL,
            {headers:{
                'Accept': 'application/json',
            }}
        );

        if (!imgPath_raw.ok) {
            console.error(`Failed to fetch images for result ${ai_result_index}: HTTP ${imgPath_raw.status}`);
            return; // Skip this iteration
        }

        var imgPaths = await imgPath_raw.json();

        var imgPathList = [];
        imgPaths.forEach( (imgPath) => {
            var thePath = `${imgPathURL}/${imgPath.url}`;

            imgPathList.push(thePath);
        });

        result_card_list[ai_result_index] = resultCard_factory(
                ai_result.family,
                // ai_result_index,
                ai_result.probability,
                ai_result.part,
                ai_result.make,
                ai_result.directory,
                imgPathList
            );
        
    }));
    // After the Promise.all, filter out any undefined entries that may have resulted from skipped iterations
    result_card_list = result_card_list.filter(card => card !== undefined);
    
    // console.log(result_card_list);
    globalThis.result_card_list = result_card_list;

    renderResultCards(result_card_list);

    document.getElementById("savePathPlaceholder").innerHTML = resultAI_savePlace;

}


async function click_camShotAndPost(){
    
    document.getElementById('camShotAndPost').disabled = true;
    document.getElementById('camShotAndPost').innerHTML = "馬達運作中";

    // First do camera shot
    var motorSPListItems = motorSPlist.children;
    var listSPvalue = [];
    for (let i = 0; i < motorSPListItems.length; i++) {
        const element = motorSPListItems[i];
        var SPvalue = element.children[0].value;
        listSPvalue.push(SPvalue);
        
        console.log(SPvalue);
    }

    // Call existing camera shot function
    let response = await fetch(`/cam/shot`,{
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(listSPvalue)
    });
    let jsonRes = await response.json();
    console.log(jsonRes);

    console.log("start change slide content");

    // Update slides using existing code
    splide1.remove( range(0, splide1.length, 1) );
    splide2.remove( range(0, splide2.length, 1) );
    
    for(var i = 0; i < jsonRes['cam1'].length; i++) {
        let tempChind1 = `<li class="splide__slide"><img src="data:image/webp;base64,${jsonRes['cam1'][i]}"></li>`;
        splide1.add( tempChind1 );
        let tempChind2 = `<li class="splide__slide"><img src="data:image/webp;base64,${jsonRes['cam2'][i]}"></li>`;
        splide2.add( tempChind2 );
    }

    document.getElementById('camShotAndPost').innerHTML = "結果辨識中";

    // Call existing result button function
    await click_resultButton();

    document.getElementById('camShotAndPost').disabled = false;
    document.getElementById('camShotAndPost').innerHTML = "拍照並辨識";
}


async function onclickCorrectLabel(){
    var correctLabel_String = document.getElementById("correctLabelInput").value;
    if (correctLabel_String.length == 0){
        document.getElementById("savePathPlaceholder").innerHTML = "下面欄位請填入標籤訊息";
        return false;
    }

    let response = await fetch(`/correctLabel?correctLabel=${correctLabel_String}`,{
        method: 'POST',
    });
    let jsonRes = await response.json();
    console.log(jsonRes);
    var strSavePlace = document.getElementById("savePathPlaceholder");
    if(jsonRes == true){
        strSavePlace.innerHTML += "儲存label完成";
    }else{
        strSavePlace.innerHTML += "儲存label失敗";
    }
}



function reloadWs(){
    wsAddrPort = wsAddrInput.value;
    wsMotorData.close();
    wsCam1.close();
    wsCam2.close();
    wsMotorData     = null;
    wsCam1          = null;
    wsCam2          = null;

    setTimeout(()=>{
        if(wsAddrPort.indexOf(':') != -1) {
            wsMotorData = new WebSocket(`ws://${wsAddrPort}/ws/motor/data`);
            wsCam1 = new WebSocket(`ws://${wsAddrPort}/ws/cam/1`);    
            wsCam2 = new WebSocket(`ws://${wsAddrPort}/ws/cam/2`);    
        }else{
            wsMotorData = new WebSocket(`wss://${wsAddrPort}/ws/motor/data`);
            wsCam1 = new WebSocket(`wss://${wsAddrPort}/ws/cam/1`);
            wsCam2 = new WebSocket(`wss://${wsAddrPort}/ws/cam/2`);    
        }

        wsMotorData.onmessage = callbackWsMotorData;
        wsCam1.onmessage = callbackWsCamera_1;
        wsCam2.onmessage = callbackWsCamera_2;
        
        
    }, 1000);

}


// 加入websocket連結
wsMotorData.onmessage = callbackWsMotorData;
wsCam1.onmessage = callbackWsCamera_1;
wsCam2.onmessage = callbackWsCamera_2;

async function intilize() { 
    var intiSP = await fetch('/motor/spInit');
    var intiSPJson = await intiSP.json();
    for (let i = 0; i < intiSPJson.length; i++) {
        click_motorSP_add(intiSPJson[i]);
    }
    console.log("intilize");
    console.log(intiSPJson)
}
intilize();
