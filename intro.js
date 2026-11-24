(() => {
  const canvas = document.getElementById('world');
  const display = canvas;
  const displayCtx = display.getContext('2d', { alpha: false });
  const source = document.createElement('canvas');
  // Native Mega Drive-sized framebuffer. Legacy scene coordinates are mapped 3:2
  // onto this 320x224 surface; no post-render downsampling is performed.
  source.width = 320; source.height = 224;
  const ctx = source.getContext('2d', { alpha: false });
  ctx.imageSmoothingEnabled = false;
  ctx.setTransform(2/3,0,0,2/3,0,0);
  display.width = 320; display.height = 224;
  displayCtx.imageSmoothingEnabled = false;

  // Four Mega Drive-style 16-entry palette banks; slot zero is reserved per bank.
  const palette = [
    '#10121c','#202536','#30364a','#45465a','#625365','#85636a','#ad776e','#d09376',
    '#e7b28a','#f2d2a0','#73816f','#536b68','#3b505c','#293b4a','#172b39',
    '#17131c','#29202a','#40303a','#5b3b42','#805047','#a8614b','#ca7955','#e29a69',
    '#edbd83','#f2d69a','#d7a66d','#b78358','#8b5b46','#68443e','#49353b','#302b35',
    '#111923','#202d3b','#314655','#49616b','#668079','#89947a','#b1a27a','#d0b486',
    '#e7d0a0','#f4e1b4','#a64e42','#c4654d','#df8557','#e9a66e','#8a9b82','#5d765e',
    '#131923','#242936','#373545','#51434d','#70505a','#96636a','#bd7b70','#d99a80',
    '#edc091','#f5d9a5','#a9a06f','#7e8d68','#5d7658','#435849','#34443f','#252b32'
  ];
  const paletteBanks = Array.from({length:4},(_,bank)=>palette
    .slice(bank*16,(bank+1)*16).slice(1)
    .map(hex=>[1,3,5].map(i=>Math.round(parseInt(hex.slice(i,i+2),16)*7/255)*255/7)));
  const paletteRgb = paletteBanks.flat();
  const paletteCache = new Map();
  function quantizeCanvasToBank(targetCtx,width,height,bankIndex){
    const frame=targetCtx.getImageData(0,0,width,height),data=frame.data;
    const bank=paletteBanks[bankIndex];
    for(let i=0;i<data.length;i+=4){
      let best=0,dist=Infinity;
      for(let p=0;p<bank.length;p++){
        const c=bank[p],dr=data[i]-c[0],dg=data[i+1]-c[1],db=data[i+2]-c[2];
        const d=dr*dr+dg*dg+db*db;
        if(d<dist){dist=d;best=p;}
      }
      const c=bank[best];data[i]=c[0];data[i+1]=c[1];data[i+2]=c[2];
    }
    targetCtx.putImageData(frame,0,0);
  }
  function presentFrame() {
    const frame = ctx.getImageData(0,0,320,224);
    const data = frame.data;
    for(let i=0;i<data.length;i+=4){
      const key=(data[i]<<16)|(data[i+1]<<8)|data[i+2];
      let mapped=paletteCache.get(key);
      if(mapped===undefined){
        let best=0,dist=Infinity;
        for(let p=0;p<paletteRgb.length;p++){
          const c=paletteRgb[p],dr=data[i]-c[0],dg=data[i+1]-c[1],db=data[i+2]-c[2];
          const d=dr*dr+dg*dg+db*db;
          if(d<dist){dist=d;best=p;}
        }
        mapped=best;paletteCache.set(key,mapped);
      }
      const c=paletteRgb[mapped];
      data[i]=c[0];data[i+1]=c[1];data[i+2]=c[2];
    }
    displayCtx.putImageData(frame,0,0);
  }
  const opening = document.getElementById('opening');
  const cuneiform = document.getElementById('cuneiform');
  const title = document.getElementById('game-title');
  const W = 480, H = 270;
  let start = 0, skipped = false, lastFrame = 0;

  const C = {
    sky0:'#171b2d', sky1:'#343044', sky2:'#6b4140', dusk:'#a45c48',
    deep:'#171820', shadow:'#211c25', wall0:'#493039', wall1:'#684044',
    brick:'#9b6048', brickHi:'#d18a5b', brickLit:'#efb878',
    sand:'#b78358', sandHi:'#e2b477', sandDark:'#63413b',
    teal:'#55766c', tealHi:'#91a18a', blue:'#536578',
    cloth:'#a94e43', clothHi:'#df8557', gold:'#e5b46e',
    lamp:'#ffd58a', black:'#15151d', skin:'#d9a06c'
  };

  // Reusable 8x8 native-pixel tiles: first real tilemap pass for the bazaar floor.
  const tileColors = {
    '.':'#382930','a':'#59403a','b':'#4b3535','c':'#2b252e',
    'd':'#624542','e':'#55403e','f':'#a27555','g':'#87604b',
    'h':'#795047','i':'#bd805b','j':'#493139','k':'#684044'
  };
  const tilePatterns = {
    floor0:['aaaaaaaa','a..a..a.','a..a..a.','aaaaaaaa','..bb..bb','..bb..bb','bbbbbbbb','b..b..b.'],
    floor1:['a..a..a.','aaaaaaaa','..bb..bb','bbbbbbbb','b..b..b.','bbbbbbbb','..bb..bb','aaaaaaaa'],
    floor2:['aaaaaaaa','a..a..a.','a..a..a.','aaagaaaa','..bb..bb','..bb..bb','bbbbbbbb','b..b..b.'],
    floor3:['aaaaaaaa','a..a..a.','aaafaaaa','aaaaaaaa','..bb..bb','..bb..bb','bbbbbbbb','b..b..b.'],
    brick0:['kkkkkkkk','k..k..k.','k..k..k.','kkkkkkkk','..jj..jj','..jj..jj','jjjjjjjj','j..j..j.'],
    brick1:['kkkkkkkk','..k..k..','..k..k..','kkkkkkkk','jj..jj..','jj..jj..','jjjjjjjj','..j..j..'],
    brick2:['kkkkkkkk','k...k...','k...k...','kkkkkkkk','jjjjjjjj','..j..j..','..j..j..','jjjjjjjj'],
    brick3:['kkkkkkkk','...k...k','...k...k','kkkkkkkk','..jj..jj','..jj..jj','jjjjjjjj','jj..jj..']
  };
  const tileAtlas = {};
  Object.entries(tilePatterns).forEach(([name,rows])=>{
    const tile=document.createElement('canvas');tile.width=8;tile.height=8;
    const tileCtx=tile.getContext('2d');
    rows.forEach((row,y)=>[...row].forEach((key,x)=>{
      tileCtx.fillStyle=tileColors[key]||'#382930';
      tileCtx.fillRect(x,y,1,1);
    }));
    // Each 8x8 tile is quantized into one dedicated 15-color hardware-style bank.
    const tileBank=name.startsWith('floor')?0:1;
    quantizeCanvasToBank(tileCtx,8,8,tileBank);
    tileAtlas[name]=tile;
  });
  function drawNativeTilemap(rows,nativeX,nativeY){
    rows.forEach((row,ty)=>[...row].forEach((tileName,tx)=>{
      const tile=tileAtlas[tileName];
      if(tile)ctx.drawImage(tile,(nativeX+tx*8)*1.5,(nativeY+ty*8)*1.5,12,12);
    }));
  }
  const marketFloorMap = Array.from({length:7},(_,row)=>
    Array.from({length:40},(_,col)=>['floor0','floor1','floor2','floor3'][(row*3+col*5+Math.floor(col/4))%4]).join('')
  );

  // Legacy scene coordinates are 3:2 relative to the native 320x224 framebuffer.
  // Snap every primitive to native pixel boundaries before the 2/3 transform is applied.
  const snapNative = value => Math.round(value * 2 / 3) * 1.5;
  const px = (x,y,w,h,c) => {
    const sx=snapNative(x),sy=snapNative(y);
    const sw=Math.max(1.5,snapNative(w)),sh=Math.max(1.5,snapNative(h));
    ctx.fillStyle=c;
    ctx.fillRect(sx,sy,sw,sh);
  };
  const line = (x1,y1,x2,y2,c) => {
    ctx.strokeStyle=c;ctx.lineWidth=1.5;ctx.beginPath();
    ctx.moveTo(snapNative(x1)+.75,snapNative(y1)+.75);
    ctx.lineTo(snapNative(x2)+.75,snapNative(y2)+.75);
    ctx.stroke();
  };
  function seeded(n){const v=Math.sin(n*127.1+311.7)*43758.5453;return v-Math.floor(v);}
  function brickWall(x,y,w,h,rows=5,seed=0){
    // Repeated 8x8 stone tiles, with alternating bond to break vertical seams.
    const tileNames=['brick0','brick1','brick2','brick3'];
    const tileStep=12; // 8 native pixels represented in legacy scene coordinates.
    for(let yy=0,row=0;yy<h;yy+=tileStep,row++){
      const offset=row%2?6:0;
      for(let xx=-offset;xx<w;xx+=tileStep){
        const tile=tileAtlas[tileNames[(row+Math.floor((xx+offset)/tileStep)+seed)%tileNames.length]];
        if(tile)ctx.drawImage(tile,snapNative(x+xx),snapNative(y+yy),tileStep,tileStep);
      }
    }
    // A sharply stepped coping stone and dark foundation keep the silhouette readable.
    px(x-2,y,w+4,3,'#d69a68');
    px(x,y+h-2,w,2,'#30232a');
  }
  function arch(x,y,w,h,color,inside){
    // A stepped 1-native-pixel arch: no vector arcs or antialiased curves.
    const crown=Math.max(2,Math.floor(w/3));
    for(let row=0;row<crown;row++){
      const inset=crown-row-1;
      px(x+inset,y+row,w-inset*2,1,color);
    }
    px(x,y+crown,w,h-crown,color);
    const innerX=x+3,innerY=y+3,innerW=Math.max(3,w-6),innerH=Math.max(3,h-3);
    const innerCrown=Math.max(1,Math.floor(innerW/3));
    for(let row=0;row<innerCrown;row++){
      const inset=innerCrown-row-1;
      px(innerX+inset,innerY+row,innerW-inset*2,1,inside);
    }
    px(innerX,innerY+innerCrown,innerW,innerH-innerCrown,inside);
    px(x-2,y+h-3,w+4,3,'#d09a68');
  }
  function drawMoon(){
    px(365,20,44,44,'#a74745');px(370,14,36,7,'#c45e4d');
    px(373,24,31,31,'#d06c52');px(378,20,24,4,'#ed9a68');
    px(383,31,6,4,'#efb17a');px(395,43,8,6,'#a34b47');
    px(372,51,29,6,'#713c43');px(380,58,14,3,'#512f3a');
    // Small crater pixels.
    px(379,29,4,3,'#b85b4d');px(399,37,3,3,'#b85b4d');px(389,49,5,2,'#b85b4d');
  }
  function drawSky(t){
    // Four hard-edged sky bands: no gradients or alpha blending.
    px(0,0,W,58,C.sky0);px(0,58,W,38,C.sky1);
    px(0,96,W,35,C.sky2);px(0,131,W,H-131,'#3b2930');
    px(0,90,480,18,'#4a3540');px(0,108,480,9,'#684047');
    for(let i=0;i<66;i++){
      const x=(i*73+17)%480,y=(i*37+11)%100;
      if(i%4!==0)px(x,y,1+(i%3===0?1:0),1,'#d4a17b');
    }
    drawMoon();
    // Wispy cloud silhouettes.
    for(let i=0;i<5;i++){
      const x=(i*113+((t*.003)%520))-35,y=62+(i%3)*13;
      if(i%2===0){px(x,y,42,1,'#684047');px(x+8,y-3,20,1,'#6b4140');}
    }
  }
  function drawZiggurat(){
    // Massive stepped Babylonian ziggurat, left skyline.
    const tiers=[
      [7,144,139,17,'#765047'],[17,126,120,18,'#946047'],
      [28,108,99,18,'#a86c4d'],[40,91,76,17,'#865244'],
      [51,76,54,15,'#b27650'],[62,63,32,13,'#9b6048']
    ];
    tiers.forEach(([x,y,w,h,c],i)=>{
      brickWall(x,y,w,h,Math.max(2,Math.ceil(h/12)),i+2);
      px(x-2,y,w+4,3,i%2?'#e0a06b':'#c98559');
      px(x+4,y+h-3,w-8,3,'#543941');
      // Recessed slit windows are carved into the masonry as crisp dark pixels.
      for(let bx=x+7;bx<x+w-6;bx+=26){
        px(bx,y+5,5,5,'#583b3d');px(bx+1,y+6,3,2,'#d18b5e');
      }
    });
    // Shrine at the summit.
    px(68,48,21,16,'#c88a5b');px(65,46,27,4,'#e2ae74');
    px(72,39,13,8,'#a9664d');px(76,33,5,7,'#d69a67');
    px(73,53,11,9,'#302630');px(77,55,3,7,'#e8b477');
    // Processional stairway and side retaining walls.
    for(let i=0;i<7;i++){px(24+i*6,145-i*10,5,3,'#e3a56c');}
    px(3,160,146,3,'#bd8057');
    // tiny banner.
    px(88,39,1,18,'#d6a16d');px(89,40,10,6,'#a64b43');px(89,46,7,2,'#e2b477');
  }
  function drawGardens(){
    // Hanging Gardens: layered retaining walls and lush terraces.
    const tiers=[
      [337,128,132,24],[350,106,112,22],[365,87,87,19],[380,70,60,17]
    ];
    tiers.forEach(([x,y,w,h],i)=>{
      brickWall(x,y,w,h,3,i+8);
      px(x-4,y-3,w+8,4,'#d39a67');px(x+3,y+h-2,w-6,3,'#34252b');
      for(let k=0;k<Math.floor(w/20);k++){
        const tx=x+7+k*19,ty=y-9-(k%2)*5;
        px(tx,ty+8,3,8,'#4b6849');
        px(tx-4,ty+2,10,7,k%2?'#5e8052':'#75905a');
        px(tx-2,ty-2,7,5,'#8da36a');
        px(tx+3,ty+4,4,3,'#a2a66e');
      }
      // Water channel glints.
      px(x+10,y+1,w-20,2,'#8eb0a0');px(x+18,y+4,Math.max(8,w-48),1,'#c0c49a');
    });
    // Cascading vines.
    for(let i=0;i<8;i++){
      const x=352+i*15,y=126+(i%3)*7;
      px(x,y,2,9+(i%3)*3,'#435d42');px(x-2,y+5,3,2,'#81945b');
    }
    // Temple facade on the far right.
    px(432,53,40,26,'#8d5948');px(427,51,49,5,'#d29a68');
    px(435,43,33,9,'#a86b50');px(441,35,21,8,'#d49b66');
    px(447,29,9,7,'#b87c58');px(450,22,3,8,'#e1b27a');
    for(let x=436;x<470;x+=10){px(x,61,4,16,'#52363b');px(x+1,63,2,13,'#c18a61');}
    px(430,78,48,4,'#d59b67');
  }
  function drawCity(){
    // Silhouetted roofs behind the market.
    const houses=[
      [130,143,55,38],[190,151,43,31],[237,138,53,45],[287,150,43,34],
      [405,145,26,36],[0,151,35,32]
    ];
    houses.forEach(([x,y,w,h],i)=>{
      // City facades share the same reusable masonry atlas as the ziggurat.
      brickWall(x,y,w,h,Math.max(2,Math.ceil(h/12)),i+6);
      px(x-3,y-4,w+6,4,'#93604a');
      px(x+4,y+7,w-8,2,'#bd8057');
      for(let xx=x+7;xx<x+w-6;xx+=14){
        arch(xx,y+10,8,16,'#d09376','#211d27');
        px(xx+3,y+13,2,8,'#7a4c42');
        px(xx+2,y+12,3,1,'#e0a06b');
      }
      px(x+2,y+h-4,w-4,4,'#30252c');
    });
    // Distant lit windows.
    [[145,161],[169,160],[204,168],[251,156],[271,168],[414,162]].forEach(([x,y])=>{
      px(x,y,4,6,'#e8aa69');px(x+1,y+1,2,4,'#ffd18a');
    });
    // City wall crenellations.
    px(0,178,480,12,'#3b2b33');
    for(let x=0;x<480;x+=22){px(x,173,14,7,'#795047');px(x+2,175,10,2,'#bd805b');}
    for(let x=12;x<480;x+=44){px(x,182,5,8,'#201e27');}
  }
  function drawBazaarLife(t){
    // A string of small market pennants breaks the skyline and gives the street scale.
    line(54,139,424,145,'#382a30');
    const flags=['#b65345','#d0a05f','#607b68','#a95a43','#b98a57','#6e8170'];
    for(let i=0;i<10;i++){
      const x=66+i*37;
      const y=139+Math.round((x-54)*.016);
      px(x,y,9,2,'#3b2b31');
      px(x+2,y+2,6,7,flags[i%flags.length]);
      px(x+2,y+8,3,3,flags[i%flags.length]);
      px(x+3,y+3,3,1,'#e4bd83');
    }
    // Tiny merchants and visitors: kept behind the stalls so the traveler remains the hero.
    const people=[
      {x:108,y:160,robe:'#557064',hood:'#29252b'},
      {x:238,y:158,robe:'#a65a43',hood:'#30242a'},
      {x:326,y:163,robe:'#9b7950',hood:'#29232a'},
      {x:455,y:158,robe:'#586c70',hood:'#29232a'}
    ];
    people.forEach((p,i)=>{
      const bob=Math.round(Math.sin(t*.002+i*1.8)*1);
      const x=p.x,y=p.y+bob;
      // Hood, face, shoulders and long robe.
      px(x+3,y,7,5,p.hood);px(x+4,y+2,5,5,'#d6a675');
      px(x+5,y+3,1,1,'#29232a');px(x+8,y+3,1,1,'#29232a');
      px(x+2,y+6,9,4,p.robe);px(x+1,y+9,11,9,p.robe);
      px(x+3,y+10,2,6,'#d2a16d');px(x+8,y+10,2,6,'#30272b');
      px(x+2,y+17,4,2,'#30252b');px(x+8,y+17,4,2,'#30252b');
      // A small lantern or basket gives each silhouette a readable action.
      if(i===1){px(x+12,y+9,3,5,'#b9784b');px(x+13,y+10,1,2,'#ffd28a');}
      else if(i===2){px(x-3,y+13,5,4,'#bd8a56');px(x-2,y+12,3,1,'#e1b87d');}
      else{px(x+10,y+10,3,2,'#e0b77a');}
      // Individual merchant silhouettes: hood piping, face shadow, belt, sleeves and footwear.
      px(x+4,y+1,5,1,'#e8bd80');
      px(x+3,y+4,1,3,'#594039');px(x+9,y+4,1,2,'#594039');
      px(x+5,y+6,4,1,'#875044');
      px(x+4,y+8,2,2,'#e8bd80');px(x+8,y+8,2,2,'#e8bd80');
      px(x+2,y+11,2,4,'#30252c');px(x+9,y+11,2,4,'#30252c');
      px(x+3,y+15,7,1,'#e0b477');
      px(x+5,y+15,1,2,'#d69a68');px(x+8,y+15,1,2,'#d69a68');
      px(x+3,y+18,4,1,'#201e27');px(x+8,y+18,4,1,'#201e27');
      if(i===0){
        // Spice seller: rolled sleeves and a small bronze weighing scale.
        px(x+1,y+8,3,2,'#d6a675');px(x+10,y+8,3,2,'#d6a675');
        px(x+12,y+7,1,5,'#d5a45f');px(x+10,y+7,5,1,'#e8bd80');
        px(x+11,y+12,4,2,'#a8614b');
      }else if(i===1){
        // Lamp merchant: embroidered sash and a glowing pendant.
        px(x+4,y+9,5,1,'#f0c58a');px(x+6,y+10,2,3,'#d69a68');
        px(x+7,y+12,2,2,'#ffd28a');
      }else if(i===2){
        // Basket carrier: shoulder strap and woven pack.
        px(x+8,y+6,2,8,'#d5a45f');px(x+10,y+8,4,5,'#52665a');
        px(x+11,y+9,2,1,'#e0b477');px(x+11,y+11,2,1,'#e0b477');
      }else{
        // Gate watcher: dark shoulder mantle and a short bronze staff.
        px(x+2,y+6,8,2,'#38444a');px(x+1,y+8,2,7,'#38444a');
        px(x+13,y+7,1,13,'#d5a45f');px(x+12,y+7,3,1,'#e8bd80');
      }
    });
    // Hanging bundles of herbs and woven goods beneath the awnings.
    for(let i=0;i<5;i++){
      const x=147+i*48;
      line(x,151,x,163,'#4b3932');
      px(x-3,162,7,5,i%2?'#6b8058':'#8c7950');
      px(x-2,160,5,2,'#a9a16b');
      px(x-1,167,3,2,'#4e684b');
    }
  }

  function drawLamassu(){
    // Monumental winged bull guardian on a raised plinth, fully readable silhouette.
    px(281,174,65,7,'#2d252b');px(285,171,57,3,'#c28a5b');
    // Body and haunch.
    px(293,145,39,25,'#c49a6d');px(300,139,28,10,'#dfb77f');
    px(296,151,31,14,'#e3c28e');px(291,161,39,8,'#a97855');
    // Four legs, carved hooves.
    px(296,163,7,13,'#e0b981');px(307,163,6,13,'#d2a16d');
    px(321,163,7,13,'#e6c48e');px(330,160,5,16,'#c18b60');
    [296,307,321,330].forEach(x=>{px(x,174,7,3,'#47343a');px(x+1,172,5,2,'#f0d19a');});
    // Human-like bearded head and horned crown.
    px(300,126,24,19,'#d8ad7b');px(304,121,17,9,'#e8c995');
    px(302,117,5,7,'#b77e56');px(318,117,5,7,'#b77e56');
    px(307,113,3,8,'#e6c18a');px(316,113,3,8,'#e6c18a');
    px(306,124,4,3,'#2a252b');px(318,124,4,3,'#2a252b');
    px(309,130,10,3,'#795044');px(307,134,15,5,'#9a644b');
    for(let i=0;i<4;i++)px(309+i*3,136+i%2,2,5,'#e0bd89');
    // Layered feathered wings.
    for(let i=0;i<6;i++){
      px(282+i*3,143-i*3,12,4,i%2?'#e5c58e':'#b98b62');
      px(279+i*3,148-i*2,10,3,'#8f694f');
    }
    px(278,140,16,5,'#e4c28b');px(280,135,12,4,'#d8b17c');
    // Decorative carved bands.
    for(let i=0;i<5;i++)px(296+i*6,155,3,2,'#896148');
    px(288,177,54,2,'#d2a06c');
  }
  function drawStall(s,index){
    const {x,y,w,h=45,cloth}=s;
    // Stall shadow, posts, counter.
    px(x-5,y+12,w+10,h,'#241f27');
    px(x,y+10,w,30,'#714535');px(x+3,y+13,w-6,24,'#9a6041');
    px(x+2,y+30,w-4,4,'#d49a62');px(x-4,y+34,w+8,5,'#3b292d');
    px(x+3,y+9,3,35,'#4b3030');px(x+w-6,y+9,3,35,'#4b3030');
    // Canopy with scalloped edge and sewn stripes.
    px(x-7,y,w+14,5,cloth);px(x-5,y+4,w+10,8,cloth);
    for(let xx=x-5,k=0;xx<x+w+5;xx+=12,k++){
      const stripe=k%2===0?'#e4b77c':(index===1?'#5b6e64':'#713d3d');
      px(xx,y+1,6,10,stripe);px(xx+1,y+10,4,3,cloth);
      px(xx+2,y+12,2,2,'#e4b77c');
    }
    px(x-7,y,w+14,2,'#f0c58a');
    // Canopy underside, stitched seams and side drapes add depth to the awning.
    px(x-5,y+11,w+10,2,'#4a3030');
    for(let xx=x+7;xx<x+w-5;xx+=24){
      px(xx,y+5,1,6,'#f1c58a');
      px(xx+2,y+6,2,4,'#6d3c38');
    }
    px(x-3,y+12,4,18,'#6f3c37');
    px(x+w-1,y+12,4,18,'#6f3c37');
    px(x+2,y+29,w-4,2,'#e0ac70');
    // Goods: jars, baskets, cloth rolls, produce, pottery.
    for(let i=0;i<6;i++){
      const gx=x+7+i* Math.max(10,(w-18)/6),gy=y+19+(i%2)*3;
      const colors=['#d3a05e','#7e9b7d','#b85c46','#e3c28b','#647d84','#bd8054'];
      px(gx,gy+3,7,8,colors[(i+index)%6]);px(gx+1,gy,5,4,colors[(i+index)%6]);
      px(gx+2,gy-2,3,3,'#e5c38b');px(gx+1,gy+10,6,1,'#36272a');
    }
    // Hanging textiles and price tags.
    px(x+Math.floor(w*.28),y+12,13,3,'#e5bd83');px(x+Math.floor(w*.28),y+15,2,7,'#a84f43');
    px(x+Math.floor(w*.7),y+12,12,3,'#8ba08a');px(x+Math.floor(w*.7),y+15,2,7,'#d2a56c');
    // Warm interior and layered counter edge.
    px(x+8,y+15,w-16,2,'#e0a46c');
    px(x+3,y+34,w-6,2,'#e2b477');
    px(x+5,y+36,w-10,2,'#5b3935');
    for(let xx=x+8;xx<x+w-8;xx+=18){
      px(xx,y+38,2,4,'#3a292d');
      px(xx+1,y+38,1,3,'#b47a50');
    }
    // Hanging little lanterns at the stall corners.
    [x+10,x+w-13].forEach((lx,i)=>{
      px(lx,y+10,1,5,'#33252b');
      px(lx-2,y+14,5,5,'#a75a3f');
      px(lx-1,y+15,3,3,'#ffd28a');
      px(lx,y+16,1,2,'#fff0bf');
    });
  }
  function drawMarket(t){
    // Main market street and foreground stalls.
    px(0,190,480,80,'#382930');
    px(0,192,480,8,'#60403a');
    // Native 8x8 tilemap replaces the former smooth-gradient ground plane.
    drawNativeTilemap(marketFloorMap,0,132);
    for(let y=203;y<270;y+=8){
      const perspective=(y-200)/70;
      line(0,y,480,y,'#87604b');
      const step=17+Math.floor(perspective*22);
      for(let x=(y%16?7:0);x<480;x+=step){
        const ww=Math.max(7,step-3);
        px(x,y+1,ww,5+Math.floor(perspective*2),((x+y)%3===0)?'#624542':'#55403e');
        px(x+2,y+1,Math.max(3,ww-5),1,'#a27555');
      }
    }
    // Converging perspective seams.
    for(let x=-100;x<600;x+=82)line(240+(x-240)*.08,200,x,270,'#382d32');
    // scattered straw, footprints and spilled grain.
    for(let i=0;i<48;i++){
      const x=(i*67+13)%480,y=207+(i*29)%61;
      px(x,y,1+(i%3===0?1:0),1,i%2?'#bd8b5e':'#9d7956');
    }
    for(let i=0;i<7;i++){px(165+i*5,243+(i%2)*3,2,1,'#e0b77a');}
    // distant awnings establish a busy bazaar silhouette.
    drawStall({x:8,y:177,w:94,h:48,cloth:'#a94e43'},0);
    drawStall({x:128,y:181,w:92,h:45,cloth:'#c08a4e'},1);
    drawStall({x:359,y:176,w:112,h:49,cloth:'#9b5146'},2);
    // central spice merchant's smaller stand.
    px(226,190,54,26,'#4c3030');px(222,187,62,5,'#d39a5f');
    px(228,192,50,3,'#9a6041');
    for(let i=0;i<5;i++){
      px(230+i*9,199+(i%2)*2,6,7,['#c08b4d','#7f9670','#b65c47','#d8b578','#6f8584'][i]);
    }
    // Lanterns, hooks and suspended signboards.
    const lamps=[34,116,245,335,442];
    lamps.forEach((x,i)=>{
      const y=157+(i%2)*8;
      const flicker=.82+.18*Math.sin(t*.009+i*2.1);
      // Stepped lantern light pool uses solid palette colors, never alpha gradients.
      if(flicker>.88){
        px(x-4,y+12,8,3,'#a8614b');px(x-8,y+15,16,2,'#805047');
        px(x-12,y+17,24,1,'#5b3b42');
      }else{
        px(x-3,y+12,6,2,'#805047');px(x-7,y+14,14,2,'#5b3b42');
      }
      px(x,y-9,1,13,'#31242a');px(x-4,y+1,9,2,'#d6a16b');
      px(x-4,y+3,9,8,'#a95d43');px(x-2,y+4,5,5,'#ffd28a');
      px(x-1,y+5,2,3,'#fff0bf');px(x,y+9,2,4,'#e6a45e');
      // Hard-edged reflected light on the stone floor.
      px(x-10,194,20,2,'#d09376');
      px(x-16,197,32,2,'#805047');
      px(x-8,200,16,1,'#a8614b');
    });
    // Market signs in simple painted pictograms.
    px(17,166,18,9,'#d8b178');px(19,168,14,2,'#6c3d37');px(24,171,4,3,'#a84f43');
    px(390,164,21,10,'#c99560');px(393,166,15,2,'#60403a');px(398,169,5,3,'#6e8170');
    // foreground rugs and baskets.
    px(18,231,54,5,'#8c4c43');px(22,233,46,2,'#d8a36b');
    for(let i=0;i<5;i++){px(22+i*10,231,2,5,'#e7bd80');}
    px(389,229,43,10,'#624033');px(393,226,34,4,'#b97a4e');
    for(let i=0;i<4;i++){px(397+i*8,227,4,4,'#d7a45f');}
    // Foreground pottery on the left: layered rims, shoulders and painted bands.
    const pots=[
      {x:79,y:238,w:12,h:20,c:'#a85d45'},
      {x:94,y:244,w:10,h:14,c:'#6c7d70'},
      {x:66,y:248,w:9,h:11,c:'#c28b56'}
    ];
    pots.forEach((p,i)=>{
      px(p.x+2,p.y,p.w-4,3,'#e0b47b');
      px(p.x,p.y+3,p.w,p.h-7,p.c);
      px(p.x+1,p.y+p.h-5,p.w-2,3,i===1?'#435b56':'#70443b');
      px(p.x+2,p.y+4,p.w-4,2,'#e5b77b');
      px(p.x+2,p.y+9,p.w-4,2,i===1?'#b5b18a':'#d28a59');
      px(p.x+3,p.y+2,2,p.h-7,'#f0c68b');
    });
    // Right foreground woven baskets and folded rugs, with strong pixel silhouettes.
    px(435,238,31,20,'#49312f');px(432,235,36,5,'#b77a4d');
    for(let y=241;y<256;y+=4){
      px(437,y,27,2,'#c08a55');px(439,y+2,23,1,'#e0b77a');
    }
    px(438,233,25,3,'#6c4a3b');px(441,230,20,3,'#d0a06a');
    px(443,227,16,3,'#8c4c43');px(445,225,12,2,'#e2b77c');
    // A few bright grains and tiny stone chips catch the foreground light.
    for(let i=0;i<12;i++){
      const x=145+i*17,y=250+(i%3)*4;
      px(x,y,2,1,i%2?'#d7a96e':'#e8c18a');
    }
  }
  // Hand-placed architectural pixel details: relief bands, glazed inlays and carved trim.
  function drawArchitectureDetails(t){
    // Ziggurat: recessed courses and repeated sun-disk reliefs break up broad brick faces.
    const courses=[[12,143,128],[22,125,112],[33,107,92],[45,90,70],[56,75,49],[67,62,28]];
    courses.forEach(([x,y,w],row)=>{
      px(x+3,y+5,w-6,1,'#5b3b3d');
      px(x+5,y+7,w-10,1,row%2?'#d09376':'#bd8057');
      for(let xx=x+13+(row%2?8:0);xx<x+w-9;xx+=24){
        px(xx,y+9,5,1,'#e2b477');
        px(xx+1,y+8,3,3,'#805047');
        px(xx+2,y+9,1,1,'#f0c58a');
      }
    });
    // Summit shrine: stepped lintel, inset doorway and tiny ceremonial flame.
    px(69,46,19,1,'#f0c58a');px(71,44,15,1,'#e0a06a');
    px(75,49,7,8,'#241e27');px(77,50,3,6,'#d09376');
    px(78,47,1,2,'#ffd58a');px(76,57,5,1,'#e8b477');
    // Hanging Gardens: terracotta planter lips, leaf clusters and stone drain mouths.
    for(let i=0;i<6;i++){
      const x=355+i*19,y=104+(i%3)*7;
      px(x,y,8,2,'#d69a68');px(x+1,y+2,6,2,'#684044');
      px(x+2,y-3,2,3,'#8da36a');px(x+4,y-5,3,3,'#a2a66e');
      px(x+7,y-2,2,2,'#5e8052');
    }
    for(let i=0;i<4;i++){
      const x=365+i*23,y=123+(i%2)*8;
      px(x,y,5,3,'#2d3434');px(x+1,y+1,3,1,'#91b0a0');
      px(x+1,y+3,3,1,'#d0a06a');
    }
    // Temple facade: column capitals, dark joints and a stepped frieze.
    for(let x=436;x<470;x+=10){
      px(x-1,59,6,2,'#edbd83');px(x,64,1,10,'#e0b477');
      px(x+3,64,1,10,'#6b4140');px(x-1,76,6,2,'#e7b28a');
    }
    px(431,49,45,1,'#f0c58a');px(438,40,29,1,'#f0c58a');
    // Distant houses: roof coping, timber lintels and alternating warm/cool window depth.
    const windows=[[145,161],[169,160],[204,168],[251,156],[271,168],[414,162]];
    windows.forEach(([x,y],i)=>{
      px(x-1,y-1,6,1,'#d99a69');
      px(x+1,y+1,1,4,i%2?'#fff0bf':'#f2c17b');
      px(x+3,y+2,1,3,'#805047');
      px(x-1,y+6,6,1,'#493139');
    });
    // Small roof finials and parapet notches give the skyline a hand-built silhouette.
    [[136,139],[184,147],[232,134],[283,146],[405,141],[12,147]].forEach(([x,y],i)=>{
      px(x,y,2,5,'#d09376');px(x-2,y+3,6,1,'#e0b477');
      if(i%2===0)px(x,y-2,2,2,'#edbd83');
    });
  }

  function drawMonumentDetails(){
    // Lamassu relief: feather divisions, harness studs and a carved plinth inscription.
    for(let i=0;i<6;i++){
      px(281+i*3,142-i*2,2,1,'#f0d19a');
      px(284+i*3,149-i,2,1,'#705047');
    }
    for(let i=0;i<5;i++){
      px(298+i*6,158,2,2,'#e9c17b');
      px(299+i*6,160,1,2,'#49353b');
    }
    px(292,179,48,1,'#e8bd80');
    for(let i=0;i<8;i++)px(296+i*5,181,2,1,i%2?'#bd8057':'#d69a68');
  }

  // Foreground craft pass: embroidery, pottery marks, basket weave and stall joinery.
  function drawMarketDetails(t){
    // Left rug: stepped border and a repeating diamond pattern.
    px(20,230,50,1,'#f0c58a');px(20,237,50,1,'#493139');
    for(let i=0;i<6;i++){
      const x=24+i*8;
      px(x,232,2,2,'#e8bd80');px(x+2,234,2,2,'#6c3938');
      px(x+1,236,2,1,'#f0c58a');
    }
    // Right folded carpet: contrasting woven stripes and fringe.
    for(let i=0;i<5;i++){
      const y=231+i*2;
      px(392,y,31,1,i%2?'#e0b477':'#8c4c43');
    }
    for(let x=394;x<425;x+=5)px(x,240,2,2,'#e8bd80');
    // Pottery: painted chevrons, neck rings and dark mouths.
    const marks=[[79,238,12],[94,244,10],[66,248,9]];
    marks.forEach(([x,y,w],i)=>{
      px(x+Math.floor(w/2)-1,y+1,3,1,'#493139');
      px(x+2,y+6,w-4,1,'#f0c58a');
      px(x+2,y+8,2,2,'#6c3938');px(x+w-4,y+8,2,2,'#6c3938');
      px(x+Math.floor(w/2)-1,y+10,2,2,'#e8bd80');
    });
    // Basket weave on the right: alternating over-under rows and reinforced rim.
    for(let row=0;row<4;row++){
      for(let col=0;col<6;col++){
        px(438+col*4,242+row*3,2,1,(row+col)%2?'#e0b477':'#a66a47');
      }
    }
    px(436,240,27,1,'#e8bd80');px(438,255,23,1,'#30252c');
    // Stall canopy seams and tiny tassels; their one-pixel sway stays on the 12fps grid.
    [8,128,359].forEach((x,i)=>{
      const y=[177,181,176][i],w=[94,92,112][i];
      for(let k=0;k<Math.floor(w/24);k++){
        const tx=x+12+k*24;
        px(tx,y+11,1,4,'#f0c58a');
        px(tx-1,y+14,3,1,'#6c3938');
      }
      const sway=Math.round(Math.sin(t*.006+i)*1);
      px(x+Math.floor(w/2)+sway,y+12,2,3,'#e8bd80');
    });
    // Tiny spice bowls on the central counter: rims, contents and shadow pixels.
    const spice=['#c66b4c','#d8b578','#7f9670','#a95d43','#6f8584'];
    for(let i=0;i<5;i++){
      const x=230+i*9,y=199+(i%2)*2;
      px(x-1,y,8,1,'#e8bd80');
      px(x+1,y+2,4,2,spice[i]);
      px(x+2,y+1,2,1,'#f0c58a');
      px(x,y+6,7,1,'#30252c');
    }
    // Scattered date pits and grain form deliberate clusters instead of random noise.
    [[148,252],[153,255],[160,251],[174,258],[181,254],[188,260],[204,253],[211,257]].forEach(([x,y],i)=>{
      px(x,y,2,1,i%3===0?'#f0c58a':'#c08a55');
      if(i%2===0)px(x+2,y+1,1,1,'#684044');
    });
  }

  function drawAtmosphere(t){
    // Low amber haze softens the far end of the street without washing out pixels.
    for(let i=0;i<7;i++){
      const x=(i*91+(t*.006)%540)-30,y=184+(i%3)*13;
      if(i%2===0)px(x,y,65,1,'#805047');
    }
    // Thin cooking-smoke ribbons drift sideways from the market roofs.
    const chimneys=[{x:76,y:174},{x:181,y:178},{x:397,y:171}];
    chimneys.forEach((p,i)=>{
      for(let k=0;k<5;k++){
        const drift=(t*.008+i*19+k*13)%30;
        const rise=(t*.012+k*8+i*5)%34;
        const width=5+(k%3)*3;
        if(k%2===0){
          px(p.x+Math.round(drift*.45)-Math.round(rise*.12),p.y-rise,width,1,'#805047');
          px(p.x+Math.round(drift*.45)+3,p.y-rise-2,width-2,1,'#684044');
        }
      }
    });
    // A slow ribbon of warm air moves above the paving, broken into pixel bands.
    for(let i=0;i<4;i++){
      const x=(i*137+t*.018)%540-40;
      const y=204+i*7+Math.sin(t*.0015+i)*2;
      if(i%2===0){px(x,y,38,1,'#a8614b');px(x+9,y+2,21,1,'#805047');}
    }
    // Floating dust motes catch the lantern light; some brighten as they cross it.
    for(let i=0;i<38;i++){
      const x=(i*83+(t*.012*(i%3+1)))%480;
      const y=(i*47+Math.sin(t*.001+i)*5)%205;
      const pulse=.18+seeded(i)*.35+Math.max(0,Math.sin(t*.002+i))*.12;
      if(pulse>.42)px(x,y,1+(i%9===0?1:0),1,i%3===0?'#e7b28a':'#d09376');
    }
    // Stepped corner shadows replace the modern radial vignette.
    for(let i=0;i<8;i++){
      const inset=i*3;
      px(inset,inset,34-i*3,2,'#17131c');px(W-34+ i*3,inset,34-i*3,2,'#17131c');
      px(inset,H-inset-2,34-i*3,2,'#17131c');px(W-34+i*3,H-inset-2,34-i*3,2,'#17131c');
    }
  }
  function background(t){
    drawSky(t);drawZiggurat();drawGardens();drawCity();drawArchitectureDetails(t);
    drawBazaarLife(t);drawLamassu();drawMonumentDetails();drawMarket(t);drawMarketDetails(t);drawAtmosphere(t);
  }

  // A compact, hand-drawn traveler sprite with readable silhouette and layered cloth.
  const traveler = [
    '......HHHH......',
    '.....HHHHHH.....',
    '.....HSSSSH.....',
    '......SSSS......',
    '.....SSSSSS.....',
    '....SSSSSSSS....',
    '....SSSSSSSS....',
    '.....SSSSSS.....',
    '......RR........',
    '.....RRRR.......',
    '....RRRRRR......',
    '...RRRRRRRR.....',
    '...RRRRRRRR.....',
    '....RRRRRR......',
    '.....RRRR.......',
    '.....RR.RR......',
    '....LL...LL.....',
    '....LL...LL.....',
    '...LL.....LL....',
    '...LL.....LL....',
    '..LL.......LL...'
  ];
  // Four-frame 16x24 native-pixel sprite sheet: idle, left stride, passing, right stride.
  const travelerSheet=document.createElement('canvas');
  travelerSheet.width=64;travelerSheet.height=24;
  const travelerSheetCtx=travelerSheet.getContext('2d');
  const travelerColors={H:'#29232a',S:'#e3b77e',R:'#a64e42',L:'#25232b'};
  for(let frame=0;frame<4;frame++){
    const phase=frame*Math.PI/2;
    traveler.forEach((row,ry)=>[...row].forEach((ch,rx)=>{
      if(ch==='.'||!travelerColors[ch])return;
      let dx=rx,dy=ry;
      if(ry>=16){
        const leg=rx<8?0:1;
        const shift=Math.round(Math.sin(phase+(leg?Math.PI:0)));
        dx=Math.max(0,Math.min(15,rx+shift));
        dy=ry-(Math.max(0,Math.round(Math.cos(phase+(leg?Math.PI:0))))>0&&ry>=18?1:0);
      }
      travelerSheetCtx.fillStyle=travelerColors[ch];
      travelerSheetCtx.fillRect(frame*16+dx,dy,1,1);
    }));
    // A one-pixel boot highlight gives the tiny silhouette a readable ground contact.
    travelerSheetCtx.fillStyle='#d2a16d';
    travelerSheetCtx.fillRect(frame*16+4,22,4,1);
    travelerSheetCtx.fillRect(frame*16+11,22,4,1);
  }
  // The traveler atlas has its own sprite palette bank, independent of background tiles.
  quantizeCanvasToBank(travelerSheetCtx,64,24,2);
  function drawTravelerFrame(x,y,scale,gait){
    const frame=((Math.floor(gait/(Math.PI/2))%4)+4)%4;
    ctx.drawImage(travelerSheet,frame*16,0,16,24,
      snapNative(x),snapNative(y),
      Math.max(1.5,snapNative(16*scale)),Math.max(1.5,snapNative(24*scale)));
  }

  function drawTravelerShadow(x,y,scale=2,weight=1){
    // Three stepped layers keep the ground contact crisp at the canvas pixel scale.
    px(x+4*scale,y,10*scale,2,'#17131c');
    px(x+2*scale,y+2,14*scale,2,'#17131c');
    px(x,y+4,18*scale,1,'#202536');
  }

  function drawTravelerCraft(x,y,scale=2,gait=0){
    // Fine pixel-art pass: layered hood, beard, embroidered cloak, belt and travel gear.
    const s=scale,phase=Math.floor(gait/(Math.PI/2))%4;
    // Hood rim and folded cloth around the cheek.
    px(x+5*s,y+1*s,7*s,1*s,'#e8bd80');
    px(x+4*s,y+2*s,1*s,4*s,'#684044');
    px(x+12*s,y+2*s,1*s,3*s,'#684044');
    px(x+6*s,y+5*s,5*s,1*s,'#c18a61');
    px(x+7*s,y+6*s,4*s,1*s,'#875044');
    // Beard silhouette and two warm highlights make the profile legible at native size.
    px(x+8*s,y+6*s,4*s,2*s,'#49353b');
    px(x+9*s,y+8*s,3*s,2*s,'#684044');
    px(x+9*s,y+8*s,1*s,1*s,'#d69a68');
    px(x+11*s,y+9*s,1*s,1*s,'#d69a68');
    // Layered shoulder mantle and stitched edge of the cloak.
    px(x+3*s,y+8*s,2*s,5*s,'#684044');
    px(x+4*s,y+9*s,1*s,4*s,'#d09376');
    px(x+5*s,y+11*s,7*s,1*s,'#e8bd80');
    px(x+4*s,y+13*s,9*s,1*s,'#49353b');
    px(x+5*s,y+14*s,1*s,4*s,'#e0a06b');
    px(x+7*s,y+15*s,1*s,3*s,'#d09376');
    px(x+10*s,y+14*s,1*s,4*s,'#e0a06b');
    px(x+12*s,y+13*s,1*s,4*s,'#684044');
    // Woven sash, bronze buckle and alternating stitch marks.
    px(x+5*s,y+12*s,8*s,1*s,'#e8bd80');
    px(x+8*s,y+11*s,2*s,3*s,'#49353b');
    px(x+8*s,y+12*s,1*s,1*s,'#f2d69a');
    for(let i=0;i<4;i++)px(x+(5+i*2)*s,y+14*s,1*s,1*s,i%2?'#f0c58a':'#d69a68');
    // Satchel has a flap, seam, clasp and a tightly rolled blanket.
    px(x+12*s,y+7*s,3*s,1*s,'#d0b486');
    px(x+12*s,y+8*s,3*s,3*s,'#52665a');
    px(x+13*s,y+9*s,1*s,1*s,'#a9a06f');
    px(x+14*s,y+10*s,1*s,1*s,'#e8bd80');
    px(x+13*s,y+11*s,2*s,1*s,'#302b35');
    px(x+3*s,y+9*s,2*s,5*s,'#536b68');
    px(x+3*s,y+10*s,1*s,3*s,'#a9a06f');
    // Boots, sole glints and tiny gait-dependent dust scuffs.
    px(x+4*s,y+20*s,4*s,1*s,'#49353b');
    px(x+10*s,y+20*s,5*s,1*s,'#49353b');
    px(x+(phase%2?4:5)*s,y+19*s,2*s,1*s,'#e8bd80');
    px(x+(phase%2?11:12)*s,y+19*s,2*s,1*s,'#e8bd80');
  }

  function drawTraveler(x,y,scale=2,fallen=false,gait=0){
    if(fallen){
      // Side-on exhausted merchant: readable hood, face, beard, robe, arm, pack and boots.
      px(x+1*scale,y+6*scale,11*scale,10*scale,'#29232a');
      px(x+3*scale,y+7*scale,8*scale,7*scale,'#e3b77e');
      px(x+8*scale,y+9*scale,2*scale,2*scale,'#34252a');
      px(x+8*scale,y+12*scale,4*scale,2*scale,'#875044');
      px(x+5*scale,y+13*scale,7*scale,3*scale,'#765044');
      px(x+6*scale,y+15*scale,2*scale,2*scale,'#e0b47c');
      px(x+2*scale,y+5*scale,8*scale,2*scale,'#f0c58a');
      px(x+3*scale,y+4*scale,6*scale,1*scale,'#34252a');
      px(x+11*scale,y+8*scale,18*scale,10*scale,'#a64e42');
      px(x+14*scale,y+7*scale,12*scale,2*scale,'#e0a06a');
      px(x+16*scale,y+10*scale,9*scale,1*scale,'#cf7650');
      px(x+18*scale,y+14*scale,8*scale,2*scale,'#6c3938');
      px(x+13*scale,y+17*scale,14*scale,3*scale,'#6d785d');
      px(x+17*scale,y+18*scale,9*scale,2*scale,'#b4a078');
      px(x+15*scale,y+14*scale,10*scale,2*scale,'#e3b77e');
      px(x+23*scale,y+14*scale,3*scale,2*scale,'#f0c58a');
      // Woven travel satchel, stitched flap and bronze clasp.
      px(x+22*scale,y+5*scale,7*scale,7*scale,'#52665a');
      px(x+23*scale,y+6*scale,5*scale,4*scale,'#829071');
      px(x+24*scale,y+10*scale,3*scale,1*scale,'#d5a45f');
      px(x+28*scale,y+10*scale,8*scale,4*scale,'#25232b');
      px(x+34*scale,y+13*scale,6*scale,3*scale,'#d2a16d');
      px(x+35*scale,y+14*scale,4*scale,1*scale,'#f0c58a');
      px(x+3*scale,y+15*scale,7*scale,2*scale,'#25232b');
      return;
    }
    // Base body and all four gait poses come from the dedicated native sprite sheet.
    drawTravelerFrame(x,y,scale,gait);
    // Face, hood highlights and traveler's scarf.
    px(x+7*scale,y+2*scale,5*scale,scale,'#f1cc91');
    px(x+8*scale,y+3*scale,2,2,'#34252a');
    px(x+5*scale,y+5*scale,7*scale,scale,'#f0c68a');
    px(x+4*scale,y+8*scale,9*scale,scale,'#d58a57');
    px(x+5*scale,y+10*scale,7*scale,scale,'#c66b4c');
    px(x+4*scale,y+12*scale,2*scale,5*scale,'#e3ae70');
    // Pack and rolled blanket.
    px(x+12*scale,y+7*scale,3*scale,6*scale,'#5b6b5c');
    px(x+13*scale,y+8*scale,2*scale,3*scale,'#9a9a72');
    px(x+3*scale,y+9*scale,2*scale,6*scale,'#3d3434');
    // Woven cloak: hem, folds and a narrow bronze-trimmed travel belt.
    px(x+4*scale,y+14*scale,9*scale,1,'#713d39');
    px(x+5*scale,y+15*scale,1*scale,4*scale,'#e2a16a');
    px(x+8*scale,y+14*scale,1*scale,5*scale,'#783d38');
    px(x+11*scale,y+15*scale,1*scale,4*scale,'#e2a16a');
    px(x+5*scale,y+13*scale,8*scale,1*scale,'#e0b477');
    px(x+8*scale,y+13*scale,2*scale,2*scale,'#e9c17b');
    px(x+9*scale,y+14*scale,1*scale,1*scale,'#49332e');
    // Hood seam, cheek highlight and a clearer eye/nose silhouette.
    px(x+6*scale,y+1*scale,1*scale,3*scale,'#594039');
    px(x+7*scale,y+4*scale,4*scale,1*scale,'#f5d59e');
    px(x+10*scale,y+3*scale,1*scale,1*scale,'#30232a');
    px(x+12*scale,y+4*scale,1*scale,2*scale,'#d18a57');
    // Satchel strap crosses the shoulder; bronze clasp catches the lantern light.
    px(x+11*scale,y+6*scale,1*scale,7*scale,'#d5a45f');
    px(x+12*scale,y+10*scale,2*scale,1*scale,'#e8c17c');
    px(x+13*scale,y+12*scale,1*scale,2*scale,'#3e5148');
    // Clear outline pixels separate figure from the background.
    px(x+5*scale,y+1*scale,7*scale,1,'#f2d19a');
    px(x+4*scale,y+6*scale,1,8*scale,'#f0c68a');
    px(x+13*scale,y+11*scale,1,5*scale,'#f0c68a');
    drawTravelerCraft(x,y,scale,gait);
    if(fallen){
      px(x+5*scale,y+17*scale,9*scale,3*scale,'#a64e42');
      px(x+11*scale,y+18*scale,6*scale,2*scale,'#29232a');
      px(x+15*scale,y+19*scale,5*scale,2*scale,'#d4a16d');
      px(x+2*scale,y+15*scale,5*scale,2*scale,'#e3b77e');
    }
  }
  function drawTravelerStopped(x,y,scale=2,t=0){
    drawTraveler(x,y,scale,false,0);
    // A deliberate planted stance: both boots level, one hand settles on the belt.
    px(x+4*scale,y+19*scale,5*scale,1*scale,'#29232a');
    px(x+10*scale,y+19*scale,5*scale,1*scale,'#29232a');
    px(x+11*scale,y+10*scale,2*scale,3*scale,'#d69a68');
    px(x+10*scale,y+12*scale,3*scale,1*scale,'#f0c58a');
    px(x+6*scale,y+7*scale,1*scale,2*scale,'#30252c');
    // Subtle breath: a single shoulder pixel changes on the native 12fps beat.
    if(Math.floor(t/83)%2===0)px(x+4*scale,y+8*scale,2*scale,1*scale,'#e8bd80');
  }

  function drawTravelerRecovery(x,y,scale=2,progress=0){
    const s=scale,p=Math.max(0,Math.min(1,progress));
    // A low kneel that rises from one braced hand; proportions stay on the 16px grid.
    const headY=Math.round(5-p*2),bodyY=Math.round(10-p*3),legY=Math.round(18-p*2);
    // Grounded cloak and rear leg.
    px(x+3*s,y+legY*s,9*s,3*s,'#29232a');
    px(x+4*s,y+(legY-1)*s,6*s,2*s,'#684044');
    px(x+10*s,y+(legY-2)*s,5*s,2*s,'#49353b');
    // Torso, mantle and embroidered edge.
    px(x+4*s,y+bodyY*s,9*s,7*s,'#a64e42');
    px(x+5*s,y+(bodyY+1)*s,7*s,4*s,'#c66b4c');
    px(x+4*s,y+(bodyY+5)*s,9*s,1*s,'#e8bd80');
    px(x+6*s,y+(bodyY+2)*s,1*s,3*s,'#f0c58a');
    px(x+10*s,y+(bodyY+2)*s,1*s,3*s,'#684044');
    // Hood, face and beard, kept consistent with the walking sprite palette.
    px(x+6*s,y+headY*s,7*s,4*s,'#29232a');
    px(x+7*s,y+(headY+1)*s,5*s,2*s,'#e3b77e');
    px(x+9*s,y+(headY+2)*s,3*s,1*s,'#49353b');
    px(x+10*s,y+(headY+2)*s,1*s,1*s,'#f0c58a');
    px(x+8*s,y+(headY+3)*s,4*s,1*s,'#684044');
    // Bracing palm moves from the ground to the thigh as he gets upright.
    const handX=Math.round(1+(p*3));
    px(x+handX*s,y+(bodyY+5)*s,3*s,2*s,'#e3b77e');
    px(x+(handX+1)*s,y+(bodyY+6)*s,2*s,1*s,'#f0c58a');
    // Travel pack stays behind the shoulder, with its bronze clasp visible.
    px(x+13*s,y+(bodyY-1)*s,4*s,6*s,'#52665a');
    px(x+14*s,y+bodyY*s,2*s,2*s,'#829071');
    px(x+15*s,y+(bodyY+3)*s,1*s,1*s,'#e8bd80');
    // One bent knee and planted boot establish the recovery silhouette.
    px(x+7*s,y+(legY-2)*s,5*s,2*s,'#d09376');
    px(x+11*s,y+(legY-1)*s,5*s,2*s,'#29232a');
    px(x+12*s,y+legY*s,4*s,1*s,'#e8bd80');
  }

  function dust(x,y,amount,t){
    for(let i=0;i<36;i++){
      const a=i*2.399,d=(i*17%53)*amount;
      const xx=x+Math.cos(a)*d+Math.sin(t*.004+i)*2;
      const yy=y+Math.sin(a)*d*.32+Math.cos(t*.006+i)*2;
      if(amount>.2)px(xx,yy,1+(i%3===0?1:0),1,i%2?'#e7b28a':'#d09376');
    }
  }
  function draw(ts){
    if(ts-lastFrame < 1000/12){requestAnimationFrame(draw);return;}
    lastFrame=ts;
    const e=ts-start;
    background(ts);
    let sx=0,sy=0;
    if(e<8500){
      const walkEnd=8100;
      const p=Math.max(0,Math.min(1,e/walkEnd));
      const x=-42+p*250;
      const step=Math.floor(e/330)%2;
      const wobble=Math.sin(e*.035)*1.25;
      const limp=Math.abs(Math.sin(e*.018))*2.1;
      drawTravelerShadow(Math.round(x)+2,220,2,1);
      if(e<walkEnd){
        drawTraveler(Math.round(x),178+Math.round(wobble+limp),2,false,e*.019);
      }else{
        // He stops, catches his breath and braces a hand against the travel belt.
        drawTravelerStopped(Math.round(x),178,2,e);
        if(Math.floor(e/165)%3===0)px(x+34,168,2,1,'#e8bd80');
      }
      // Scuffed footprints and dragging dust trail.
      if(step===0){px(x-6,207,13,1,'#805047');px(x-12,211,7,1,'#684044');}
      if(e>3000&&e<8500)px(x-24,204,18,1,'#805047');
    }else if(e<9150){
      const p=Math.max(0,Math.min(1,(e-8500)/650));
      const shake=Math.sin(e*.09)*(1-p)*2;
      drawTravelerShadow(201,250,2,1.25);
      ctx.save();
      ctx.translate(226+shake,225+Math.abs(shake));
      ctx.rotate(p*1.48);
      drawTraveler(-14,-20,2,false);
      ctx.restore();
      // A short dust burst marks the impact, then settles into a few pixels.
      dust(218,254,Math.min(1,p),ts);
    }else if(e<11600){
      const tremble=Math.sin(e*.09)*.7;
      drawTravelerShadow(193,260,2,1.3);
      drawTraveler(194+tremble,226+Math.abs(tremble),2,true);
      if(e<10100)dust(218,255,.55,ts);
      // One shoulder pixel and the fingers twitch before the traveler gathers strength.
      if(Math.floor(e/250)%2===0)px(220,245,2,1,'#e8bd80');
    }else if(e<12600){
      const p=(e-11600)/1000;
      drawTravelerShadow(193,260,2,1.15);
      drawTravelerRecovery(194,218,2,p);
      if(p<.55)px(190,258,5,1,'#d09376');
    }else{
      // He reaches a low, exhausted kneel rather than snapping back to a full idle pose.
      drawTravelerShadow(193,260,2,1.05);
      drawTravelerRecovery(194,218,2,1);
      if(Math.floor(e/500)%2===0)px(218,235,1,1,'#f0c58a');
    }
    // Sand gust carries the cuneiform away.
    if(e>14800&&e<16600){
      const amount=Math.min(1,(e-14800)/400);
      dust(240,132,amount,ts);
      for(let i=0;i<65;i++){
        const x=(i*23+e*.052)%480,y=92+(i*17)%91;
        px(x,y,1+(i%3===0?1:0),1,'#e8c18a');
      }
      sx=Math.sin(ts*.11)*2.2;sy=Math.cos(ts*.09)*1.3;
    }
    presentFrame();
    canvas.style.transform='translate('+Math.round(sx/1.5)+'px,'+Math.round(sy/1.5)+'px)';
    if(!skipped){
      if(e>10400)opening.classList.add('visible');
      if(e>12800)cuneiform.classList.add('visible');
      if(e>15100)cuneiform.classList.remove('visible');
      if(e>16300)title.classList.add('visible');
    }
    if(e<19000)requestAnimationFrame(draw);
    else{title.classList.add('visible');}
  }
  function skip(){
    if(skipped)return;skipped=true;
    opening.classList.add('visible');cuneiform.classList.remove('visible');
    title.classList.add('visible');
  }
  document.addEventListener('keydown',e=>{
    if(e.key==='Escape'||e.key===' '||e.key==='Enter'){e.preventDefault();skip();}
  });
  // Invisible tap/click target keeps the cinematic free of UI controls.
  document.getElementById('intro').addEventListener('pointerdown',skip,{passive:true});

  // Respect reduced-motion preferences: show the finished title card immediately.
  if(window.matchMedia('(prefers-reduced-motion: reduce)').matches){
    background(0);
    presentFrame();
    opening.classList.add('visible');
    title.classList.add('visible');
  }else{
    requestAnimationFrame(ts=>{start=ts;draw(ts);});
  }
})();