(() => {
  const canvas=document.getElementById('world'),ctx=canvas.getContext('2d',{alpha:false});
  const opening=document.getElementById('opening'),cuneiform=document.getElementById('cuneiform'),title=document.getElementById('game-title'),hint=document.getElementById('skip-hint');
  const W=480,H=270;let start=0,skipped=false;
  const px=(x,y,w,h,c)=>{ctx.fillStyle=c;ctx.fillRect(Math.round(x),Math.round(y),Math.max(1,Math.round(w)),Math.max(1,Math.round(h)))};
  function background(t){
    const g=ctx.createLinearGradient(0,0,0,H);g.addColorStop(0,'#14111a');g.addColorStop(.58,'#302027');g.addColorStop(1,'#100c11');ctx.fillStyle=g;ctx.fillRect(0,0,W,H);
    for(let i=0;i<34;i++){const x=(i*83+17)%W,y=(i*47+11)%112;if(i%4!==0)px(x,y,1,1,'#a68b79')}
    // Pixel-built blood moon.
    px(345,35,42,42,'#542b31');px(349,31,34,50,'#7d3d3b');px(354,28,25,4,'#a35b4b');px(350,38,35,28,'#914a42');px(359,34,16,4,'#b36a52');px(366,54,9,4,'#5c2d35');
    // A single stepped ziggurat mass.
    px(182,91,116,8,'#211921');px(194,99,92,15,'#28202a');px(205,114,70,14,'#30232a');px(218,128,45,14,'#38262a');px(231,142,20,10,'#412b2b');
    for(let y=100;y<159;y+=13)px(190+(y-100)*.75,y,100-(y-100)*1.5,2,'#49302e');
    px(0,150,480,120,'#110d12');
    px(0,139,66,80,'#211820');px(8,128,45,14,'#342329');px(74,151,72,72,'#20171e');px(82,139,55,14,'#39262a');
    px(340,145,76,79,'#20171e');px(349,132,58,15,'#39262a');px(420,153,60,68,'#211820');px(428,141,42,13,'#38252a');
    [18,91,310,390].forEach((x,i)=>{const y=178+(i%2)*8;px(x,y,56,55,'#3b2929');px(x-4,y-7,64,9,i%2?'#80513d':'#966044');px(x+7,y+10,5,45,'#60402f');px(x+44,y+10,5,45,'#60402f');px(x+17,y+20,25,35,'#100c11')});
    [35,119,282,365,443].forEach((x,i)=>{const y=160+(i%2)*10;px(x,y,3,9,'#d08b51');px(x-2,y+3,7,5,'#e6a15c')});
    px(0,222,480,48,'#171116');
    for(let y=228;y<270;y+=9){px(0,y,480,1,'#39262a');for(let x=(y%18?8:0);x<480;x+=32)px(x,y+1,1,7,'#2d2025')}
    const drift=(t*.004)%120;for(let i=0;i<4;i++){ctx.globalAlpha=.08;px((i*137+drift)%520-30,216+i*10,85,3,'#c4a18a')}ctx.globalAlpha=1;
  }
  // Whole 16x25 merchant sprite: hood, shoulders, robe and dragging legs share one pixel grid.
  const walkA=[
    '......HH......','.....HHHH.....','.....HHHH.....','......HH......',
    '.....CCCC.....','....CCCCCC....','....CCCCCC....','.....CCCC.....',
    '......CC......','.....CCCC.....','....CCCCCC....','...CCCCCCCC...',
    '..CCCCCCCCCC..','..CCCCCCCCCC..','...CCCCCCCC...',
    '......CC......','......CC......','.....CCCC.....',
    '....LL..LL....','....LL..LL....','....LL..LL....',
    '...LL....LL...','...LL....LL...','..LL......LL..','..LL......LL..'
  ];
  const walkB=[
    '......HH......','.....HHHH.....','.....HHHH.....','......HH......',
    '.....CCCC.....','....CCCCCC....','....CCCCCC....','.....CCCC.....',
    '......CC......','.....CCCC.....','....CCCCCC....','...CCCCCCCC...',
    '..CCCCCCCCCC..','..CCCCCCCCCC..','...CCCCCCCC...',
    '......CC......','......CC......','.....CCCC.....',
    '....LL..LL....','....LL..LL....','...LL....LL...',
    '..LL......LL..','..LL......LL..','..LL......LL..','...LL......LL.'
  ];
  const fallen=[
    '................','................','................','................',
    '................','................','................','................',
    '................','................','................','................',
    '................','................','................','................',
    '................','................','................','................',
    '....HH..........','...HHHH.........','..CCCCCCCCC.....','..CCCCCCCCCC....',
    '...LL.....LL....'
  ];
  function sprite(frame,x,y,s=2){
    const colors={H:'#171015',C:'#49302b',L:'#171015'};
    frame.forEach((row,ry)=>[...row].forEach((ch,rx)=>{if(colors[ch])px(x+rx*s,y+ry*s,s,s,colors[ch])}));
    if(frame===walkA||frame===walkB){px(x+5*s,y+4*s,5*s,s,'#76503a');px(x+4*s,y+12*s,8*s,s,'#62402f')}
    if(frame===fallen)px(x+5*s,y+21*s,5*s,s,'#76503a');
  }
  function sandBurst(t,amount){
    for(let i=0;i<58;i++){
      const seed=i*2.399,dist=(8+((i*17)%62))*amount;
      const x=240+Math.cos(seed)*dist+(t*.002*(i%3-1));
      const y=150+Math.sin(seed)*dist*.42+Math.sin(t*.008+i)*2;
      ctx.globalAlpha=Math.max(0,.85-amount*.55-(i%5)*.08);
      px(x,y,1+(i%3),1+(i%2),'#d1ad79');
    }ctx.globalAlpha=1;
  }
  function hammer(ts,e){
    if(e<14200||e>15350)return;
    const p=Math.max(0,Math.min(1,(e-14200)/850));
    const y=-28+p*146;
    ctx.save();ctx.translate(244,y);ctx.rotate(p*.08);
    // One compact pixel-art stoneworking hammer silhouette.
    px(-2,0,5,39,'#211719');px(-1,4,3,31,'#9b704b');
    px(-13,28,27,9,'#171116');px(-16,25,32,5,'#76513a');
    px(-13,21,26,4,'#b08a5b');px(-11,18,22,3,'#4b3028');
    ctx.restore();
  }
  function draw(ts){
    ctx.imageSmoothingEnabled=false;background(ts);const e=ts-start;
    if(e<8600){
      const p=Math.max(0,Math.min(1,e/7800)),x=-34+p*244,step=Math.floor(e/390)%2;
      sprite(step?walkB:walkA,Math.round(x),151+(step?1:0),2);
      if(e>400&&step===0){ctx.globalAlpha=.25;px(x-2,198,8,2,'#c8a17b');ctx.globalAlpha=1}
    }else if(e<10400){
      const p=Math.min(1,(e-8600)/650);ctx.save();ctx.translate(210,202);ctx.rotate(p*.08);sprite(fallen,-8,0,2);ctx.restore();
      if(p>.6){ctx.globalAlpha=(p-.6)*.45;px(190,221,34,2,'#b99878');px(183,224,14,1,'#b99878');ctx.globalAlpha=1}
    }else sprite(fallen,194,202,2);
    hammer(ts,e);
    if(e>14700&&e<16900)sandBurst(ts,Math.min(1,(e-14700)/450));
    if(e>=16900&&e<18400)sandBurst(ts,Math.max(0,1-(e-16900)/1500));
    for(let i=0;i<12;i++){const xx=(i*59+(ts*.006*(i%3+1)))%W,yy=205+(i*17)%55;ctx.globalAlpha=.10;px(xx,yy,1,1,'#d7b38c')}ctx.globalAlpha=1;
    // A short stone-strike shake as the cuneiform gives way to the carved title.
    if(e>14700&&e<15400)canvas.style.transform='translate('+Math.round(Math.sin(ts*.08)*3)+'px,'+Math.round(Math.cos(ts*.07)*2)+'px)';
    else canvas.style.transform='translate(0,0)';
    if(!skipped){
      if(e>10400)opening.classList.add('visible');
      if(e>12800)cuneiform.classList.add('visible');
      if(e>15100)cuneiform.classList.remove('visible');
      if(e>16400)title.classList.add('visible');
    }
    if(e<19000)requestAnimationFrame(draw);
    else {title.classList.add('visible');hint.classList.add('visible')}
  }
  function skip(){if(skipped)return;skipped=true;opening.classList.add('visible');cuneiform.classList.remove('visible');title.classList.add('visible');hint.classList.remove('visible');sprite(fallen,194,202,2)}
  hint.addEventListener('click',skip);
  document.addEventListener('keydown',e=>{if(e.key==='Escape'||e.key===' '){e.preventDefault();skip()}});
  requestAnimationFrame(ts=>{start=ts;draw(ts)});
})();