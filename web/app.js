'use strict';
const $ = id => document.getElementById(id);
const colors = {A:'#a7dba7',B:'#80c7df',C:'#efb47c'};
let busy=false, cancelled=false, statusData=null, metricData=null, polling=false, pendingControl=false;
let lastSequence=0, displayedRun=null;
const esc = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number = n => Number(n||0).toLocaleString('vi-VN',{maximumFractionDigits:1});
function notice(message,error=false){ $('notice').textContent=message; $('notice').classList.toggle('error',error); }
async function api(path,method='GET',body){
  const response=await fetch(path,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(16000)});
  let data; try {data=await response.json();}catch{throw new Error('Máy chủ trả dữ liệu không đọc được.');}
  if(!response.ok){const error=new Error(typeof data.detail==='string'?data.detail:'Dữ liệu không hợp lệ (HTTP '+response.status+').');error.status=response.status;error.data=data;throw error;}
  return data;
}
function lockControls(){
  const locked=busy||pendingControl||Boolean(metricData?.active)||Boolean(statusData?.controls_busy);
  ['algorithm','vnodes','apply','key','pattern','count','concurrency','reset','send','batch'].forEach(id=>$(id).disabled=locked);
  $('cancel').disabled=!busy;
  document.querySelectorAll('[data-action="delay"]').forEach(b=>b.disabled=locked||b.dataset.running!=='true');
}
function render(){
  if(!statusData||!metricData)return;
  const m=metricData, s=statusData;
  $('connection').textContent='Đã kết nối Python';
  $('active-algorithm').textContent=s.algorithm==='round_robin'?'ROUND ROBIN':'CONSISTENT HASHING';
  document.querySelector('.lb-node .eyebrow').textContent='PYTHON / :'+(s.port||8080);
  $('healthy-count').textContent=s.backends.filter(b=>b.status==='healthy').length+' / '+s.backends.length+' máy khỏe';
  if(displayedRun!==m.run_id){displayedRun=m.run_id;lastSequence=0;$('last-route').textContent='Đang chờ lượt đầu tiên';}
  const latest=m.logs[0];
  if(latest){lastSequence=latest.sequence;$('last-route').textContent='#'+latest.sequence+' → '+(latest.backend_id?'Máy '+latest.backend_id:'không có máy khỏe');}
  const totalAssigned=Object.values(m.backends).reduce((n,b)=>n+b.assigned,0);
  $('servers').innerHTML=s.backends.map(b=>{
    const st=m.backends[b.id]||{};
    const running=b.process_running;
    return '<article class="server '+(latest?.backend_id===b.id?'highlight':'')+'" data-server="'+esc(b.id)+'"><div class="server-top"><h3>Máy '+esc(b.id)+'</h3><span class="health '+esc(b.status)+'">'+({healthy:'Khỏe',unhealthy:'Lỗi',unknown:'Đang kiểm tra'}[b.status]||b.status)+'</span></div><p class="server-address">'+esc(b.url)+'</p><div class="server-count">'+number(st.assigned)+'<small>được phân công</small></div><div class="backend-details"><span>Đang xử lý: '+number(st.active)+'</span><span>TB: '+number(st.average_ms)+' ms</span></div><div class="track"><div class="bar" style="width:'+(totalAssigned?st.assigned/totalAssigned*100:0)+'%"></div></div><div class="server-actions"><button data-id="'+esc(b.id)+'" data-action="'+(running?'stop':'start')+'" '+(!s.managed||pendingControl?'disabled':'')+'>'+(running?'Dừng máy':'Khởi động')+'</button><button data-id="'+esc(b.id)+'" data-action="delay" data-running="'+running+'" '+(!running?'disabled':'')+'>'+ (b.delay_ms>100?'Nhanh lại':'Làm chậm')+'</button></div><div class="process-note">Độ trễ: '+number(b.delay_ms)+' ms · Tiến trình '+(running===null?'ngoài quản lý':running?'đang chạy':'đã dừng')+'<br>Health: '+b.success_streak+' lần tốt / '+b.failure_streak+' lần lỗi liên tiếp</div></article>';
  }).join('');
  $('m-total').innerHTML=number(m.total)+' <em>/ '+number(m.active)+'</em>';
  $('m-average').innerHTML=number(m.average_ms)+' <em>ms</em>';
  $('m-p95').innerHTML=number(m.p95_ms)+' <em>ms</em>';
  $('m-errors').innerHTML=number(m.errors)+' <em>/ '+number(m.success+m.errors)+'</em>';
  $('logs').innerHTML=m.logs.length?m.logs.map(r=>'<tr><td>#'+r.sequence+'</td><td class="key-cell">'+esc(r.key)+'</td><td>'+esc(r.backend_id||'—')+'</td><td>'+number(r.elapsed_ms)+' ms</td><td class="'+(r.status===200?'status-ok':'status-error')+'">'+r.status+'</td></tr>').join(''):'<tr><td colspan="5" class="empty">Chưa có yêu cầu. Nhấn “Gửi 1 yêu cầu” để bắt đầu.</td></tr>';
  $('lesson').textContent=s.algorithm==='round_robin'
    ?'Round Robin chia lượt theo danh sách máy khỏe. Khi máy C chậm, C vẫn nhận lượt; khi health check loại C, chỉ còn A và B.'
    :'Consistent Hashing giữ cùng khóa trên cùng backend khi vòng băm không đổi. Khóa quá phổ biến có thể làm một máy nhận nhiều yêu cầu.';
  lockControls();
}
async function refresh(){
  if(polling)return;
  polling=true;
  try{
    [statusData,metricData]=await Promise.all([api('/api/status'),api('/api/metrics')]);
    render();
  }catch(error){$('connection').textContent='Mất kết nối';notice('Không kết nối được Python. Kiểm tra cửa sổ chạy demo. '+error.message,true);}
  finally{polling=false;}
}
function ringSVG(data){
  const cx=150,cy=130,r=92;
  const xy=(position,radius)=>[cx+Math.cos(position*Math.PI*2-Math.PI/2)*radius,cy+Math.sin(position*Math.PI*2-Math.PI/2)*radius];
  const marks=data.nodes.map(n=>{const a=xy(n.position,r-4),b=xy(n.position,r+4);return '<line x1="'+a[0]+'" y1="'+a[1]+'" x2="'+b[0]+'" y2="'+b[1]+'" stroke="'+(colors[n.backend_id]||'#fff')+'" stroke-width="2"/>';}).join('');
  const key=xy(data.key_position,r);
  $('ring').innerHTML='<title>Vòng băm với '+data.nodes.length+' nút ảo. Khóa chọn máy '+esc(data.selected||'không có')+'.</title><circle cx="150" cy="130" r="92" fill="none" stroke="#34454b" stroke-width="1"/>'+marks+'<line x1="150" y1="130" x2="'+key[0]+'" y2="'+key[1]+'" stroke="#d5ef83" stroke-dasharray="4 5"/><circle cx="'+key[0]+'" cy="'+key[1]+'" r="6" fill="#d5ef83" stroke="#172125" stroke-width="2"/><circle cx="150" cy="130" r="41" fill="#172125"/><text x="150" y="126" text-anchor="middle" fill="#9aaba9" font-size="10">KHÓA → MÁY</text><text x="150" y="154" text-anchor="middle" fill="'+(colors[data.selected]||'#d5ef83')+'" font-size="26">'+esc(data.selected||'—')+'</text><text x="150" y="254" text-anchor="middle" fill="#9aaba9" font-size="10">A: xanh lá · B: xanh dương · C: cam</text>';
  $('ring-result').textContent=($('key').value||'user-001')+' → '+(data.selected?'Máy '+data.selected:'không có máy khỏe')+' · '+data.nodes.length+' nút ảo';
}
async function inspect(){try{ringSVG(await api('/api/hash-ring?key='+encodeURIComponent($('key').value||'user-001')));}catch(error){notice(error.message,true);}}
async function control(task,message){
  if(pendingControl)return;
  pendingControl=true;lockControls();
  try{await task();notice(message);await refresh();await inspect();}
  catch(error){notice(error.message,true);}
  finally{pendingControl=false;lockControls();}
}
$('apply').onclick=()=> {
  if(!$('vnodes').reportValidity())return;
  control(()=>api('/api/algorithm','PUT',{algorithm:$('algorithm').value,virtual_nodes:Number($('vnodes').value)}),'Đã áp dụng thuật toán và tạo lượt thống kê mới.');
};
$('algorithm').onchange=()=>notice('Lựa chọn mới chưa được áp dụng. Bấm “Áp dụng & bắt đầu lượt mới”; nhãn bên phải là thuật toán đang chạy.');
$('vnodes').onchange=()=>notice('Số nút ảo mới chưa được áp dụng. Bấm “Áp dụng & bắt đầu lượt mới” để dựng lại vòng băm.');
$('reset').onclick=()=>control(()=>api('/api/metrics/reset','POST'),'Đã xóa thống kê. Lượt Round Robin không bị đặt lại; bấm Áp dụng để bắt đầu lại từ máy đầu.');
$('servers').addEventListener('click',event=>{
  const button=event.target.closest('button[data-action]');
  if(!button||button.disabled)return;
  const id=button.dataset.id,action=button.dataset.action;
  if(action==='delay'){
    const backend=statusData.backends.find(b=>b.id===id);
    control(()=>api('/api/backends/'+id+'/delay','POST',{delay_ms:backend.delay_ms>100?100:2000}),'Đã đổi độ trễ máy '+id+' và xóa thống kê cũ.');
  }else{
    control(()=>api('/api/backends/'+id+'/process/'+action,'POST'),'Đã '+(action==='stop'?'dừng':'khởi động')+' tiến trình '+id+'. Chờ health check cập nhật trạng thái.');
  }
});
async function sendBatch(single=false){
  if(busy||pendingControl)return;
  if(!$('count').reportValidity())return;
  const base=$('key').value.trim();
  if(!base){notice('Hãy nhập khóa người dùng.',true);return;}
  const count=single?1:Number($('count').value),concurrency=single?1:Number($('concurrency').value),pattern=$('pattern').value;
  busy=true;cancelled=false;lockControls();
  let next=0,completed=0,errors=0;
  const batchId=crypto.randomUUID();
  notice('Đang gửi HTTP thật đến load balancer. Có thể dừng backend trong lúc chạy để quan sát lỗi.');
  async function worker(){
    while(!cancelled&&next<count){
      const i=next++;
      const key=single||pattern==='same'||(pattern==='hot'&&i%5!==0)?base:base.slice(0,110)+'-'+String(i+1).padStart(4,'0');
      try{await api('/api/work','POST',{request_id:batchId+'-'+i,key});}
      catch(error){errors++;if(!error.status){notice(error.message,true);cancelled=true;}}
      completed++;$('progress').textContent='Đã hoàn tất '+completed+'/'+count+' · '+errors+' lỗi';
      await refresh();
      if(concurrency===1&&next<count&&!cancelled)await new Promise(resolve=>setTimeout(resolve,180));
    }
  }
  try{await Promise.all(Array.from({length:Math.min(concurrency,count)},worker));notice((cancelled?'Đã dừng gửi thêm. ':'Hoàn tất đợt. ')+completed+' yêu cầu, '+errors+' lỗi.',errors>0);}
  finally{busy=false;await refresh();lockControls();await inspect();}
}
$('send').onclick=()=>sendBatch(true);
$('batch').onclick=()=>sendBatch(false);
$('cancel').onclick=()=>{cancelled=true;notice('Đang chờ các yêu cầu đã gửi hoàn tất; không gửi thêm.');};
$('inspect').onclick=inspect;
$('compare').onclick=async()=>{
  $('compare').disabled=true;
  try{
    const result=await api('/api/mapping-comparison');
    $('comparison').hidden=false;
    $('comparison').innerHTML='Bỏ máy <strong>'+esc(result.removed)+'</strong> · '+result.keys+' khóa · '+result.virtual_nodes+' nút ảo/backend<br>Consistent Hashing: <strong>'+number(result.consistent_hash.changed_percent)+'%</strong> khóa đổi máy &nbsp; / &nbsp; Băm % N: <strong>'+number(result.modulo.changed_percent)+'%</strong>.<br><span>Đây là kết quả tính ánh xạ, không phải kết quả đo tốc độ mạng.</span>';
  }catch(error){notice(error.message,true);}finally{$('compare').disabled=false;}
};
(async()=>{
  await refresh();
  if(statusData){$('algorithm').value=statusData.algorithm;$('vnodes').value=statusData.virtual_nodes;notice('Sẵn sàng. Đợi các backend báo Khỏe rồi gửi yêu cầu đầu tiên.');}
  await inspect();
  setInterval(refresh,700);
  setInterval(()=>{if(!document.hidden)inspect();},2500);
})();
