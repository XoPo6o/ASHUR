(() => {
 const canvas=document.getElementById('world'),ctx=canvas.getContext('2d',{alpha:false});
 const opening=document.getElementById('opening'),cuneiform=document.getElementById('cuneiform'),title=document.getElementById('game-title'),hint=document.getElementById('skip-hint');
 const W=480,H=270;let start=0,skipped=false;
 const px=(x,y,w,h,c)=>{ctx.fillStyle=c;ctx.fillRect(Math.round(x),Math.round(y),Math.max(1,Math.round(w)),Math.max(1,Math.round(h)))};
 function building(x,y,w,h,base,light){
  px(x,y,w,h,base);px(x-3,y-5,w+6,6,light);px(x+3,y+4,w-6,3,'#17151a');
  for(let xx=x+8;xx<x+w-5;xx+=Math.max(12,Math.floor(w/4))){px(xx,y+17,5,h-20,'#171319');px(xx+1,y+18,2,h-21,'#79513a')}
  px(x+4,y+h-5,w-8,5,'#24191b');
 }
 function background(t){
  const g=ctx.createLinearGradient(0,0,0,H);g.addColorStop(0,'#25243a');g.addColorStop(.48,'#68413d');g.addColorStop(1,'#211a21');ctx.fillStyle=g;ctx.fillRect(0,0,W,H);
  // Moon, stars and distant Babylon skyline.
  px(370,25,42,42,'#a94e45');px(374,21,34,50,'#d17a55');px(379,19,24,4,'#f0a16c');px(379,31,31,24,'#c96850');px(386,53,15,7,'#88403e');
  for(let i=0;i<42;i++){const x=(i*71+19)%480,y=(i*37+7)%90;if(i%3)px(x,y,2,2,'#f4c995')}
  // Babylonian stepped tower, clearly visible on the left.
  px(23,87,106,8,'#6b4540');px(30,95,92,12,'#a66b4d');px(39,107,74,13,'#865443');px(49,120,54,14,'#b07851');px(59,134,34,14,'#8c5846');px(68,148,16,12,'#c18a5b');
  for(let y=99;y<157;y+=13)px(31+(y-99)*.55,y,91-(y-99)*1.1,2,'#e1a36a');
  // Hanging Gardens terraces to the right: masonry, trees and water.
  building(342,105,112,58,'#66413c','#b17a55');
  for(let i=0;i<6;i++){const x=350+i*17;px(x,87-(i%2)*7,11,21,'#31513c');px(x+3,79-(i%2)*7,7,12,'#52744a');px(x+1,101,13,4,'#d4a16a')}
  px(338,99,120,5,'#d6a06a');px(348,119,103,4,'#c18a5b');px(358,137,82,4,'#d5a16b');
  // Temple silhouette and winged bull guardian on the far right.
  building(424,65,47,39,'#594044','#b57a57');px(432,53,31,12,'#91634f');px(440,44,15,9,'#c38b5b');
  // City wall and distant houses.
  px(0,161,480,27,'#3b2a2c');for(let x=0;x<480;x+=24){px(x,155,17,7,'#755044');px(x+4,166,3,15,'#1e1a20')}
  building(138,133,61,50,'#4b3031','#916047');building(211,143,69,42,'#503337','#a36b4d');
  // Winged bull lamassu, deliberately large and readable.
  px(289,142,34,23,'#c69a69');px(295,133,24,13,'#e0b77e');px(298,126,18,10,'#b9875c');
  px(286,148,9,22,'#e0b77e');px(317,148,10,22,'#e0b77e');px(282,139,9,13,'#e0b77e');px(321,139,9,13,'#e0b77e');
  for(let i=0;i<4;i++){px(279+i*11,145-i*3,7,3,'#f0d19a');px(279+i*11,151-i*3,7,3,'#8b6047')}
  px(296,129,3,3,'#24191b');px(312,129,3,3,'#24191b');px(301,123,12,3,'#e8c58d');
  // Market stalls in the middle ground, bright striped awnings and visible wares.
  px(0,190,480,80,'#38272a');
  const stalls=[{x:8,y:174,w:102,c:'#bd714b'},{x:128,y:180,w:92,c:'#d19a56'},{x:354,y:174,w:116,c:'#a85e4a'}];
  stalls.forEach((s,k)=>{px(s.x,s.y+12,s.w,50,'#5a3b31');px(s.x-5,s.y,s.w+10,13,s.c);for(let x=s.x;x<s.x+s.w;x+=14)px(x,s.y,5,13,k%2?'#f0c27d':'#713c38');px(s.x+7,s.y+20,s.w-14,3,'#d5a36b');for(let i=0;i<5;i++){px(s.x+10+i*15,s.y+29+(i%2)*4,8,8,['#d5a34f','#8d9a61','#b95f48','#e0bd80','#77908a'][i]);}});
  // Hanging lamps, warm light pools.
  [34,116,245,335,440].forEach((x,i)=>{const y=157+(i%2)*9;px(x,y,2,15,'#3b2522');px(x-4,y+12,10,9,'#f0a65c');px(x-2,y+14,6,5,'#ffe1a0');ctx.globalAlpha=.12;px(x-15,y+18,32,22,'#ffc16c');ctx.globalAlpha=1});
  // Foreground cobbled bazaar lane.
  px(0,224,480,46,'#493235');for(let y=228;y<270;y+=9){px(0,y,480,1,'#98664e');for(let x=(y%18?7:0);x<480;x+=29)px(x,y+1,18,6,'#5e4140')}
  // Depth haze and drifting dust.
  for(let i=0;i<4;i++){ctx.globalAlpha=.07;px((i*139+(t*.004)%130)-30,214+i*9,105,4,'#f0c99b')}ctx.globalAlpha=1;
 }
 const A=[
 '......HH......','.....HHHH.....','.....HHHH.....','......HH......','.....SSSS.....',
 '....SSSSSS....','....SSSSSS....','.....SSSS.....','......SS......','.....SSSS.....',
 '....SSSSSS....','...SSSSSSSS...','..SSSSSSSSSS..','..SSSSSSSSSS..','...SSSSSSSS...',
 '......SS......','......SS......','.....SSSS.....','....LL..LL....','....LL..LL....',
 '....LL..LL....','...LL....LL...','...LL....LL...','..LL......LL..','..LL......LL..'];
 const B=A.map((r,i)=>i===20?'...LL....LL...':i===21?'..LL......LL..':i===22?'..LL......LL..':r);
 const fallen=[
 '................','................','................','................','................',
 '................','................','................','................','................',
 '................','................','................','................','................',
 '................','................','................','................','................',
 '....HH..........','...HHHH.........','..SSSSSSSSS.....','..SSSSSSSSSS....','...LL.....LL....'];
 function sprite(frame,x,y,s=2,shake=0){
  const colors={H:'#17151a',S:'#d6a15f',L:'#262027'};
  frame.forEach((row,ry)=>[...row].forEach((ch,rx)=>{if(colors[ch])px(x+rx*s,y+ry*s,s,s,colors[ch])}));
  // Bright robe, skin and a strong outline separate the traveler from the background.
  px(x+4*s,y+5*s,8*s,s,'#f1c27b');px(x+5*s,y+6*s,6*s,3*s,'#d6a15f');
  px(x+5*s,y+10*s,6*s,2*s,'#e7b66e');px(x+4*s,y+13*s,8*s,2*s,'#b9784d');
  px(x+6*s,y+4*s,4*s,s,'#e9c18a');
  px(x+5*s,y+7*s,1,2,'#fff0c9');px(x+10*s,y+7*s,1,2,'#fff0c9');
  if(frame!==fallen){px(x+3*s,y+12*s,1,10*s,'#17151a');px(x+12*s,y+12*s,1,10*s,'#17151a')}
  if(shake){ctx.globalAlpha=.35;px(x-3,y+20*s,20*s,2,'#f5d5a0');ctx.globalAlpha=1}
 }
 function dust(x,y,amount,t){for(let i=0;i<24;i++){const a=i*2.4,d=(i*13%39)*amount;ctx.globalAlpha=Math.max(0,.8-amount*.45);px(x+Math.cos(a)*d,y+Math.sin(a)*d*.35+Math.sin(t*.01+i)*2,1+i%2,1,'#e6bd83')}ctx.globalAlpha=1}
 function draw(ts){
  const e=ts-start;background(ts);
  let sx=0,sy=0;
  if(e<8500){
   const p=Math.max(0,Math.min(1,e/7800)),x=-35+p*246,step=Math.floor(e/340)%2;
   const wobble=Math.sin(e*.035)*1.8,limp=Math.abs(Math.sin(e*.018))*2.2;
   sprite(step?B:A,Math.round(x),151+Math.round(wobble+limp),2,1);
   if(step===0){ctx.globalAlpha=.3;px(x-3,203,11,2,'#f0c58a');ctx.globalAlpha=1}
  }else if(e<10400){
   const p=Math.min(1,(e-8500)/600),shake=Math.sin(e*.09)*(1-p)*3;
   ctx.save();ctx.translate(207+shake,160+Math.abs(shake));ctx.rotate(p*.11);sprite(fallen,-8,0,2,1);ctx.restore();
   dust(211,211,Math.min(1,p),ts);
  }else{
   const tremble=e<11600?Math.sin(e*.09)*1.6:0;
   sprite(fallen,194+tremble,160+Math.abs(tremble),2,1);
   if(e<11600)dust(213,211,.55,ts);
  }
  // Wind moves the cuneiform away like grains of sand; no hammer or impact.
  if(e>14800&&e<16600){const amount=Math.min(1,(e-14800)/400);dust(240,132,amount,ts);ctx.globalAlpha=.45;for(let i=0;i<45;i++){const x=(i*23+e*.045)%480,y=95+(i*17)%85;px(x,y,1+i%2,1,'#e6c18c')}ctx.globalAlpha=1}
  if(e>14800&&e<16600){sx=Math.sin(ts*.11)*2.5;sy=Math.cos(ts*.09)*1.5}
  canvas.style.transform='translate('+Math.round(sx)+'px,'+Math.round(sy)+'px)';
  if(!skipped){
   if(e>10400)opening.classList.add('visible');
   if(e>12800)cuneiform.classList.add('visible');
   if(e>15100)cuneiform.classList.remove('visible');
   if(e>16300)title.classList.add('visible');
  }
  if(e<19000)requestAnimationFrame(draw);else{title.classList.add('visible');hint.classList.add('visible')}
 }
 function skip(){if(skipped)return;skipped=true;opening.classList.add('visible');cuneiform.classList.remove('visible');title.classList.add('visible');hint.classList.remove('visible')}
 hint.addEventListener('click',skip);
 document.addEventListener('keydown',e=>{if(e.key==='Escape'||e.key===' '){e.preventDefault();skip()}});
 requestAnimationFrame(ts=>{start=ts;draw(ts)});
})();