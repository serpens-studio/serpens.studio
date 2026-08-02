
/* mini grid in hero card */
(function(){
  var el=document.getElementById('miniGrid');if(!el)return;
  var vals=[7,5,4,4,5,8,12, 5,3,2,2,3,5,9, 4,2,1,1,2,4,7, 3,1,1,1,1,3,6, 4,2,1,1,2,4,7, 6,3,2,2,3,6,10, 9,6,5,4,6,9,14];
  vals.forEach(function(v){
    var d=document.createElement('i');
    d.style.background=v<=3?'#3E8A6E':(v<=10?'#E8A33D':'#B3401F');
    d.textContent=v;el.appendChild(d);
  });
})();

/* geo-grid demo */
(function(){
  var month0=[[0,0,0,15,0,0,0],[0,18,12,9,14,0,0],[0,13,6,4,8,17,0],[16,9,3,1,5,11,0],[0,14,7,4,9,19,0],[0,0,12,10,16,0,0],[0,0,0,18,0,0,0]];
  var month6=[[8,6,5,4,5,7,12],[6,4,3,2,3,5,9],[4,3,1,1,2,3,7],[3,2,1,1,1,2,5],[4,2,1,1,2,3,6],[6,4,3,2,3,5,10],[9,7,5,4,6,8,14]];
  var grid=document.getElementById('geoGrid'),count=document.getElementById('geoCount');
  if(!grid)return;
  var cells=[];
  for(var r=0;r<7;r++)for(var c=0;c<7;c++){
    var d=document.createElement('div');
    d.className='geo-cell'+(r===3&&c===3?' pin':'');
    grid.appendChild(d);cells.push(d);
  }
  function color(v){
    if(v===0)return['rgba(245,242,236,.18)','rgba(245,242,236,.55)'];
    if(v<=3)return['#3E8A6E','#0E1310'];
    if(v<=10)return['#E8A33D','#14120F'];
    return['#B3401F','#F5F2EC'];
  }
  function render(data){
    var top3=0;
    for(var i=0;i<49;i++){
      var v=data[Math.floor(i/7)][i%7],cl=color(v);
      cells[i].style.background=cl[0];cells[i].style.color=cl[1];
      cells[i].textContent=v===0?'–':v;
      if(v>=1&&v<=3)top3++;
    }
    count.textContent=top3+' of 49 points in the top three — '+Math.round(top3/49*100)+'% of the area';
  }
  window.setGrid=function(w){
    render(w?month6:month0);
    document.getElementById('t0').setAttribute('aria-pressed',w?'false':'true');
    document.getElementById('t6').setAttribute('aria-pressed',w?'true':'false');
  };
  render(month0);
  var flipped=false;
  if('IntersectionObserver' in window){
    new IntersectionObserver(function(es,o){
      es.forEach(function(e){
        if(e.isIntersecting&&!flipped){flipped=true;setTimeout(function(){setGrid(1)},1600);o.disconnect();}
      });
    },{threshold:.5}).observe(grid);
  }
})();

/* scroll reveal */
(function(){
  var els=document.querySelectorAll('.rev');
  if(!('IntersectionObserver' in window)||matchMedia('(prefers-reduced-motion: reduce)').matches){
    els.forEach(function(e){e.classList.add('in')});return;
  }
  var io=new IntersectionObserver(function(es){
    es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}});
  },{threshold:.12,rootMargin:'0px 0px -40px 0px'});
  els.forEach(function(e){io.observe(e)});
})();

/* lead form */
(function(){
  var form=document.getElementById('scanForm');if(!form)return;
  form.addEventListener('submit',function(ev){
    ev.preventDefault();
    if(form.website&&form.website.value)return;
    if(!form.checkValidity()){form.reportValidity();return;}
    var endpoint=form.getAttribute('action');
    var data={business:form.business.value.trim(),name:form.name.value.trim(),phone:form.phone.value.trim(),trade:form.trade.value,city:form.city.value};
    function done(){document.getElementById('formOk').style.display='block';form.querySelector('button[type=submit]').disabled=true;}
    function fallback(){
      var body='Free scan request%0D%0A%0D%0ABusiness: '+encodeURIComponent(data.business)+
        '%0D%0AName: '+encodeURIComponent(data.name)+
        '%0D%0APhone: '+encodeURIComponent(data.phone)+
        '%0D%0ATrade: '+encodeURIComponent(data.trade)+'%0D%0AArea: '+encodeURIComponent(data.city);
      location.href='mailto:{{EMAIL}}?subject='+encodeURIComponent('Free scan request — '+data.business)+'&body='+body;
      done();
    }
    if(endpoint&&endpoint!=='#'){
      fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify(data)})
        .then(function(r){if(r.ok)done();else fallback();}).catch(fallback);
    }else{fallback();}
  });
})();
