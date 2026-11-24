(() => {
  const canvas = document.getElementById('world');
  const ctx = canvas.getContext('2d', { alpha: false });
  const opening = document.getElementById('opening');
  const cuneiform = document.getElementById('cuneiform');
  const title = document.getElementById('game-title');
  const hint = document.getElementById('skip-hint');
  const W = 480, H = 270;
  let start = 0, skipped = false;

  const C = {
    sky0:'#171b2d', sky1:'#343044', sky2:'#6b4140', dusk:'#a45c48',
    deep:'#171820', shadow:'#211c25', wall0:'#493039', wall1:'#684044',
    brick:'#9b6048', brickHi:'#d18a5b', brickLit:'#efb878',
    sand:'#b78358', sandHi:'#e2b477', sandDark:'#63413b',
    teal:'#55766c', tealHi:'#91a18a', blue:'#536578',
    cloth:'#a94e43', clothHi:'#df8557', gold:'#e5b46e',
    lamp:'#ffd58a', black:'#15151d', skin:'#d9a06c'
  };
  const px = (x,y,w,h,c) => {
    ctx.fillStyle = c;
    ctx.fillRect(Math.round(x),Math.round(y),Math.max(1,Math.round(w)),Math.max(1,Math.round(h)));
  };
  const line = (x1,y1,x2,y2,c) => {
    ctx.strokeStyle=c;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x1+.5,y1+.5);ctx.lineTo(x2+.5,y2+.5);ctx.stroke();
  };
  function seeded(n){const v=Math.sin(n*127.1+311.7)*43758.5453;return v-Math.floor(v);}
  function brickWall(x,y,w,h,rows=5,seed=0){
    const rh=h/rows;
    for(let r=0;r<rows;r++){
      const off=r%2?7:0;
      for(let xx=x-off;xx<x+w;xx+=15){
        const bx=Math.max(x,xx),bw=Math.min(x+w,xx+14)-bx;
        if(bw<=0)continue;
        const v=seeded(seed+r*41+xx);
        px(bx,y+r*rh,bw,rh-1,v>.68?'#b77754':v>.32?'#965b48':'#75464a');
        px(bx+1,y+r*rh+1,Math.max(1,bw-3),1,'#d18b5b');
        if(v>.55)px(bx+Math.floor(bw*.55),y+r*rh+2,2,1,'#593b3d');
      }
    }
    px(x,y,w,2,'#d69a68');
    px(x,y+h-2,w,2,'#30232a');
  }
  function arch(x,y,w,h,color,inside){
    px(x,y+Math.floor(w/2),w,h-Math.floor(w/2),color);
    ctx.fillStyle=color;ctx.beginPath();ctx.arc(x+w/2,y+w/2,w/2,Math.PI,0);ctx.fill();
    px(x+3,y+w/2,w-6,h-w/2,inside);
    ctx.fillStyle=inside;ctx.beginPath();ctx.arc(x+w/2,y+w/2,w/2-3,Math.PI,0);ctx.fill();
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
    const g=ctx.createLinearGradient(0,0,0,H);
    g.addColorStop(0,C.sky0);g.addColorStop(.43,C.sky1);g.addColorStop(.72,C.sky2);g.addColorStop(1,'#3b2930');
    ctx.fillStyle=g;ctx.fillRect(0,0,W,H);
    // Distant haze bands.
    px(0,90,480,18,'#4a3540');px(0,108,480,9,'#684047');
    for(let i=0;i<66;i++){
      const x=(i*73+17)%480,y=(i*37+11)%100;
      if(i%4!==0)px(x,y,1+(i%3===0?1:0),1,'#d4a17b');
    }
    drawMoon();
    // Wispy cloud silhouettes.
    for(let i=0;i<5;i++){
      const x=(i*113+((t*.003)%520))-35,y=62+(i%3)*13;
      ctx.globalAlpha=.12;px(x,y,42,2,'#d58b70');px(x+8,y-3,20,2,'#d58b70');ctx.globalAlpha=1;
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
      px(x,y,w,h,c);px(x-2,y,w+4,3,i%2?'#e0a06b':'#c98559');
      px(x+4,y+h-3,w-8,3,'#543941');
      for(let bx=x+7;bx<x+w-6;bx+=13){
        px(bx,y+5,7,3,'#583b3d');px(bx+1,y+6,4,1,'#d18b5e');
      }
      for(let b=x+5;b<x+w-8;b+=25){px(b,y+9,2,4,'#d49a68');}
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
      px(x,y,w,h,i%2?'#57373a':'#493139');
      px(x-3,y-4,w+6,5,'#93604a');
      px(x+4,y+7,w-8,2,'#bd8057');
      for(let xx=x+7;xx<x+w-6;xx+=14){
        px(xx,y+14,6,12,'#211d27');px(xx+1,y+15,3,10,'#7a4c42');
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
    // Warm interior.
    px(x+8,y+15,w-16,2,'#e0a46c');
  }
  function drawMarket(t){
    // Main market street and foreground stalls.
    px(0,190,480,80,'#382930');
    px(0,192,480,8,'#60403a');
    // Ground plane with perspective paving.
    const floor=ctx.createLinearGradient(0,198,0,270);
    floor.addColorStop(0,'#59403a');floor.addColorStop(.5,'#4b3535');floor.addColorStop(1,'#2b252e');
    ctx.fillStyle=floor;ctx.fillRect(0,198,480,72);
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
      px(x,y-9,1,13,'#31242a');px(x-4,y+1,9,2,'#d6a16b');
      px(x-4,y+3,9,8,'#a95d43');px(x-2,y+4,5,5,'#ffd28a');
      px(x,y+9,2,4,'#e6a45e');
      ctx.globalAlpha=.11;px(x-17,y+10,34,24,'#ffc16b');ctx.globalAlpha=1;
      ctx.globalAlpha=.07;px(x-9,y+13,18,28,'#ffc16b');ctx.globalAlpha=1;
    });
    // Market signs in simple painted pictograms.
    px(17,166,18,9,'#d8b178');px(19,168,14,2,'#6c3d37');px(24,171,4,3,'#a84f43');
    px(390,164,21,10,'#c99560');px(393,166,15,2,'#60403a');px(398,169,5,3,'#6e8170');
    // foreground rugs and baskets.
    px(18,231,54,5,'#8c4c43');px(22,233,46,2,'#d8a36b');
    for(let i=0;i<5;i++){px(22+i*10,231,2,5,'#e7bd80');}
    px(389,229,43,10,'#624033');px(393,226,34,4,'#b97a4e');
    for(let i=0;i<4;i++){px(397+i*8,227,4,4,'#d7a45f');}
  }
  function drawAtmosphere(t){
    // Distant smoke and low amber haze.
    for(let i=0;i<7;i++){
      const x=(i*91+(t*.006)%540)-30,y=184+(i%3)*13;
      ctx.globalAlpha=.055;px(x,y,65,3,'#e5b17d');ctx.globalAlpha=1;
    }
    // Floating dust motes catch the lantern light.
    for(let i=0;i<30;i++){
      const x=(i*83+(t*.012*(i%3+1)))%480;
      const y=(i*47+Math.sin(t*.001+i)*5)%205;
      ctx.globalAlpha=.2+seeded(i)*.35;px(x,y,1,1,'#f4ca8b');
    }
    ctx.globalAlpha=1;
  }
  function background(t){
    drawSky(t);drawZiggurat();drawGardens();drawCity();drawLamassu();drawMarket(t);drawAtmosphere(t);
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
  function drawTraveler(x,y,scale=2,fallen=false){
    if(fallen){
      // Dedicated horizontal pose: hood, face, travel cloak, pack and exhausted legs.
      px(x+2*scale,y+7*scale,9*scale,7*scale,'#29232a');
      px(x+4*scale,y+10*scale,6*scale,3*scale,'#e3b77e');
      px(x+8*scale,y+10*scale,2*scale,2*scale,'#34252a');
      px(x+10*scale,y+8*scale,18*scale,10*scale,'#a64e42');
      px(x+12*scale,y+7*scale,13*scale,2*scale,'#e0a06a');
      px(x+13*scale,y+17*scale,14*scale,3*scale,'#6d785d');
      px(x+17*scale,y+18*scale,9*scale,2*scale,'#b4a078');
      px(x+26*scale,y+12*scale,7*scale,3*scale,'#25232b');
      px(x+31*scale,y+14*scale,7*scale,3*scale,'#d2a16d');
      px(x+13*scale,y+16*scale,7*scale,2*scale,'#e3b77e');
      px(x+3*scale,y+6*scale,7*scale,1,'#f2d19a');
      return;
    }
    const colors={H:'#29232a',S:'#e3b77e',R:'#a64e42',L:'#25232b'};
    traveler.forEach((row,ry)=>[...row].forEach((ch,rx)=>{
      if(ch!=='.')px(x+rx*scale,y+ry*scale,scale,scale,colors[ch]);
    }));
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
    // Clear outline pixels separate figure from the background.
    px(x+5*scale,y+1*scale,7*scale,1,'#f2d19a');
    px(x+4*scale,y+6*scale,1,8*scale,'#f0c68a');
    px(x+13*scale,y+11*scale,1,5*scale,'#f0c68a');
    if(!fallen){
      // Legs, sandals and one dragging foot.
      px(x+5*scale,y+15*scale,3*scale,5*scale,'#31272b');
      px(x+10*scale,y+15*scale,3*scale,5*scale,'#31272b');
      px(x+4*scale,y+20*scale,4*scale,2,'#d2a16d');
      px(x+11*scale,y+20*scale,5*scale,2,'#d2a16d');
      px(x+3*scale,y+21*scale,5*scale,1,'#f0c58a');
    }else{
      // Horizontal pose: body, bent knees and one exhausted arm.
      px(x+5*scale,y+17*scale,9*scale,3*scale,'#a64e42');
      px(x+11*scale,y+18*scale,6*scale,2*scale,'#29232a');
      px(x+15*scale,y+19*scale,5*scale,2*scale,'#d4a16d');
      px(x+2*scale,y+15*scale,5*scale,2*scale,'#e3b77e');
    }
  }
  function dust(x,y,amount,t){
    for(let i=0;i<36;i++){
      const a=i*2.399,d=(i*17%53)*amount;
      const xx=x+Math.cos(a)*d+Math.sin(t*.004+i)*2;
      const yy=y+Math.sin(a)*d*.32+Math.cos(t*.006+i)*2;
      ctx.globalAlpha=Math.max(0,.72-amount*.35);
      px(xx,yy,1+(i%3===0?1:0),1,'#e8c18a');
    }
    ctx.globalAlpha=1;
  }
  function draw(ts){
    const e=ts-start;
    background(ts);
    let sx=0,sy=0;
    if(e<8500){
      const p=Math.max(0,Math.min(1,e/7800));
      const x=-42+p*250;
      const step=Math.floor(e/330)%2;
      const wobble=Math.sin(e*.035)*1.25;
      const limp=Math.abs(Math.sin(e*.018))*2.1;
      px(x+5,220,25,3,'#29232b');
      drawTraveler(Math.round(x),178+Math.round(wobble+limp),2,false);
      // Scuffed footprints and dragging dust trail.
      if(step===0){ctx.globalAlpha=.4;px(x-6,207,13,2,'#d5a477');px(x-12,211,7,1,'#b98a65');ctx.globalAlpha=1;}
      if(e>3000&&e<8500){ctx.globalAlpha=.18;px(x-24,204,18,2,'#e5bc83');ctx.globalAlpha=1;}
    }else if(e<10400){
      const p=Math.min(1,(e-8500)/600);
      const shake=Math.sin(e*.09)*(1-p)*3;
      px(201,231,46,4,'#29232b');
      ctx.save();ctx.translate(207+shake,194+Math.abs(shake));ctx.rotate(p*.11);
      drawTraveler(-12,0,2,true);ctx.restore();
      dust(218,226,Math.min(1,p),ts);
    }else{
      const tremble=e<11600?Math.sin(e*.09)*1.3:0;
      px(201,231,46,4,'#29232b');
      drawTraveler(194+tremble,194+Math.abs(tremble),2,true);
      if(e<11600)dust(218,226,.55,ts);
    }
    // Sand gust carries the cuneiform away.
    if(e>14800&&e<16600){
      const amount=Math.min(1,(e-14800)/400);
      dust(240,132,amount,ts);
      ctx.globalAlpha=.55;
      for(let i=0;i<65;i++){
        const x=(i*23+e*.052)%480,y=92+(i*17)%91;
        px(x,y,1+(i%3===0?1:0),1,'#e8c18a');
      }
      ctx.globalAlpha=1;sx=Math.sin(ts*.11)*2.2;sy=Math.cos(ts*.09)*1.3;
    }
    canvas.style.transform='translate('+Math.round(sx)+'px,'+Math.round(sy)+'px)';
    if(!skipped){
      if(e>10400)opening.classList.add('visible');
      if(e>12800)cuneiform.classList.add('visible');
      if(e>15100)cuneiform.classList.remove('visible');
      if(e>16300)title.classList.add('visible');
    }
    if(e<19000)requestAnimationFrame(draw);
    else{title.classList.add('visible');hint.classList.add('visible');}
  }
  function skip(){
    if(skipped)return;skipped=true;
    opening.classList.add('visible');cuneiform.classList.remove('visible');
    title.classList.add('visible');hint.classList.remove('visible');
  }
  hint.addEventListener('click',skip);
  document.addEventListener('keydown',e=>{
    if(e.key==='Escape'||e.key===' '){e.preventDefault();skip();}
  });
  requestAnimationFrame(ts=>{start=ts;draw(ts);});
})();