(() => {
  const canvas = document.getElementById('world');
  const ctx = canvas.getContext('2d', { alpha: false });
  const opening = document.getElementById('opening');
  const cuneiform = document.getElementById('cuneiform');
  const title = document.getElementById('game-title');
  const hint = document.getElementById('skip-hint');
  const W = 480, H = 270;
  let start = 0, finished = false, skipped = false;
  const pixel = (x,y,w,h,c) => { ctx.fillStyle=c; ctx.fillRect(Math.round(x),Math.round(y),Math.round(w),Math.round(h)); };
  function background(t){
    const g=ctx.createLinearGradient(0,0,0,H);g.addColorStop(0,'#14111a');g.addColorStop(.58,'#302027');g.addColorStop(1,'#100c11');ctx.fillStyle=g;ctx.fillRect(0,0,W,H);
    for(let i=0;i<34;i++){const x=(i*83+17)%W,y=(i*47+11)%112;if((i%4)!==0)pixel(x,y,1,1,'#a68b79')}
    // Pixel-built blood moon.
    pixel(345,35,42,42,'#542b31');pixel(349,31,34,50,'#7d3d3b');pixel(354,28,25,4,'#a35b4b');pixel(350,38,35,28,'#914a42');pixel(359,34,16,4,'#b36a52');pixel(366,54,9,4,'#5c2d35');
    // One stepped ziggurat silhouette, not detached decorative shapes.
    pixel(182,91,116,8,'#211921');pixel(194,99,92,15,'#28202a');pixel(205,114,70,14,'#30232a');pixel(218,128,45,14,'#38262a');pixel(231,142,20,10,'#412b2b');
    for(let y=100;y<159;y+=13)pixel(190+(y-100)*.75,y,100-(y-100)*1.5,2,'#49302e');
    pixel(0,150,480,120,'#110d12');
    pixel(0,139,66,80,'#211820');pixel(8,128,45,14,'#342329');pixel(74,151,72,72,'#20171e');pixel(82,139,55,14,'#39262a');
    pixel(340,145,76,79,'#20171e');pixel(349,132,58,15,'#39262a');pixel(420,153,60,68,'#211820');pixel(428,141,42,13,'#38252a');
    [18,91,310,390].forEach((x,i)=>{const y=178+(i%2)*8;pixel(x,y,56,55,'#3b2929');pixel(x-4,y-7,64,9,i%2?'#80513d':'#966044');pixel(x+7,y+10,5,45,'#60402f');pixel(x+44,y+10,5,45,'#60402f');pixel(x+17,y+20,25,35,'#100c11')});
    [35,119,282,365,443].forEach((x,i)=>{const y=160+(i%2)*10;pixel(x,y,3,9,'#d08b51');pixel(x-2,y+3,7,5,'#e6a15c')});
    pixel(0,222,480,48,'#171116');
    for(let y=228;y<270;y+=9){pixel(0,y,480,1,'#39262a');for(let x=(y%18?8:0);x<480;x+=32)pixel(x,y+1,1,7,'#2d2025')}
    const drift=(t*.004)%120;for(let i=0;i<4;i++){ctx.globalAlpha=.08;pixel((i*137+drift)%520-30,216+i*10,85,3,'#c4a18a')}ctx.globalAlpha=1;
  }
  // Complete 16x25 merchant sprite. The whole silhouette is animated as one character.
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
  function drawSprite(frame,x,y,scale=2){
    const colors={H:'#171015',C:'#49302b',L:'#171015'};
    frame.forEach((row,ry)=>[...row].forEach((ch,rx)=>{if(colors[ch])pixel(x+rx*scale,y+ry*scale,scale,scale,colors[ch])}));
    if(frame===walkA||frame===walkB){pixel(x+5*scale,y+4*scale,5*scale,scale,'#76503a');pixel(x+4*scale,y+12*scale,8*scale,scale,'#62402f')}
    if(frame===fallen)pixel(x+5*scale,y+21*scale,5*scale,scale,'#76503a');
  }
  function draw(t){
    ctx.imageSmoothingEnabled=false;background(t);
    const elapsed=t-start;
    if(elapsed<8600){
      const progress=Math.max(0,Math.min(1,elapsed/7800));
      const x=-34+progress*244;
      const step=Math.floor(elapsed/390)%2;
      drawSprite(step?walkB:walkA,Math.round(x),151+(step?1:0),2);
      if(elapsed>400&&step===0){ctx.globalAlpha=.25;pixel(x-2,198,8,2,'#c8a17b');ctx.globalAlpha=1}
    }else if(elapsed<10400){
      const p=Math.min(1,(elapsed-8600)/650);
      ctx.save();ctx.translate(210,202);ctx.rotate(p*.08);drawSprite(fallen,-8,0,2);ctx.restore();
      if(p>.6){ctx.globalAlpha=(p-.6)*.45;pixel(190,221,34,2,'#b99878');pixel(183,224,14,1,'#b99878');ctx.globalAlpha=1}
    }else drawSprite(fallen,194,202,2);
    for(let i=0;i<12;i++){const xx=(i*59+(t*.006*(i%3+1)))%W;const yy=205+(i*17)%55;ctx.globalAlpha=.10;pixel(xx,yy,1,1,'#d7b38c')}ctx.globalAlpha=1;
  }
  function finish(){
    if(finished)return;finished=true;
    opening.classList.add('visible');
    setTimeout(()=>{if(!skipped)cuneiform.classList.add('visible')},1900);
    setTimeout(()=>{if(!skipped){cuneiform.classList.remove('visible');title.classList.add('visible')}},4700);
  }
  function fastForward(){
    if(skipped)return;skipped=true;finished=true;
    opening.classList.add('visible');cuneiform.classList.remove('visible');title.classList.add('visible');
    hint.classList.remove('visible');draw(start+12000);
  }
  function loop(ts){
    if(!start)start=ts;
    const elapsed=ts-start;draw(ts);
    if(elapsed>10400)finish();
    if(!finished)requestAnimationFrame(loop);
  }
  hint.addEventListener('click',fastForward);
  document.addEventListener('keydown',e=>{if(e.key==='Escape'||e.key===' '){e.preventDefault();fastForward()}});
  setTimeout(()=>hint.classList.add('visible'),1800);
  requestAnimationFrame(loop);
})();