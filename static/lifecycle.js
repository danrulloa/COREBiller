'use strict';
const previousNewQuote = newQuote, previousQuoteView = showQuote;
const previousAccountView = showAccount, previousRender = render, previousDocument = documentHtml;

newQuote = function(id){
  previousNewQuote();
  const form = $('#quote-form');
  if(!form)return;
  const q = id ? state.quotes.find(q=>q.id===id) : null;
  if(q){
    const context=JSON.parse(q.context||'{}');
    $('#modal-title').textContent='Editar '+q.number;
    for(const [key,value] of Object.entries({...context,notes:q.notes,valid_until:q.valid_until,client_id:JSON.parse(q.client).id,discount:context.discount_percent||0})){
      if(form.elements[key])form.elements[key].value=value;
    }
    lines=JSON.parse(q.items).map((item,index)=>({service_id:item.id,quantity:item.quantity,price:item.price/100,
      discount:context.line_discount_percents?.[index]||0,price_reason:item.price_reason||'Precio conservado del borrador',requirement:item.requirement||''}));
    renderLines();
  }
  const issue=form.querySelector('button:not([type])');
  issue.type='submit';issue.value='Emitida';
  issue.insertAdjacentHTML('beforebegin','<button type="submit" value="Borrador" class="ghost">Guardar borrador</button> ');
  form.onsubmit=async e=>{
    e.preventDefault();
    const saveAs=e.submitter?.value||'Borrador';
    const buttons=[...form.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);
    try{
      await api('quotes',{...Object.fromEntries(new FormData(form)),items:lines,save_as:saveAs,...(q?{id:q.id}:{})});
      $('#modal').close();view='quotes';await refresh();toast(saveAs==='Borrador'?'Borrador guardado.':'Cotización emitida.');
    }catch(error){toast(error.message,true);}finally{buttons.forEach(b=>b.disabled=false);}
  };
};

documentHtml=function(q){
  const context=JSON.parse(q.context||'{}');
  const label=q.status==='Borrador'?'BORRADOR · sin emitir':q.status==='Cancelada'?'CANCELADA · '+(context.cancel_reason||''):'';
  return (label?`<div class="notice">${esc(label)}</div>`:'')+previousDocument(q);
};

showQuote=function(id){
  previousQuoteView(id);
  const q=state.quotes.find(q=>q.id===id),actions=$('#modal-body .actions');
  if(q.status==='Borrador'){
    actions.innerHTML=permit('quotes')?'<button id="edit-draft">Editar borrador</button><button class="ghost" id="issue-draft">Emitir cotización</button><button class="ghost" id="delete-draft">Borrar borrador</button>':'';
    $('#edit-draft')?.addEventListener('click',()=>newQuote(id));
    $('#delete-draft')?.addEventListener('click',()=>{
      modal('Borrar '+q.number,'<p>Se retirará este borrador de la lista. No tiene movimientos asociados; quedará un registro en la auditoría.</p><form id="delete-draft-form"><button>Borrar borrador</button></form>');
      bindForm('#delete-draft-form','delete-draft',{id});
    });
    $('#issue-draft')?.addEventListener('click',async()=>{
      try{await api('status',{id,status:'Emitida'});$('#modal').close();await refresh();toast('Cotización emitida.');}catch(error){toast(error.message,true);}
    });
  }else if(q.status!=='Cancelada'&&permit('quotes')){
    actions.insertAdjacentHTML('beforeend','<button class="ghost" id="cancel-quote">Cancelar cotización</button>');
    $('#cancel-quote').onclick=()=>{
      modal('Cancelar '+q.number,`<form id="cancel-quote-form">${field('reason','Motivo de cancelación')}<p>Se impedirán nuevos servicios ejecutados. Los movimientos, pagos y saldos existentes se conservan; cancelar no registra devoluciones ni ajustes financieros.</p><button>Confirmar cancelación</button></form>`);
      bindForm('#cancel-quote-form','status',{id,status:'Cancelada'});
    };
  }
};

showAccount=function(id){
  previousAccountView(id);
  const q=state.quotes.find(q=>q.id===id);
  if(q.status==='Cancelada'){
    $('#modal-body [data-consume]')?.remove();
    $('#modal-body').insertAdjacentHTML('afterbegin',`<div class="notice">Cotización cancelada: ${esc(JSON.parse(q.context).cancel_reason)}. Sin nuevos servicios ejecutados; se conserva el seguimiento financiero.</div>`);
  }
};

render=function(){
  previousRender();
  if(state.settings.is_demo==='true')$('#content').insertAdjacentHTML('afterbegin','<p class="notice">EjemploCORE contiene datos ficticios y sin validez comercial. Abre la cotización de ejemplo para ver la diferencia entre cliente/contacto solicitante y responsable del proyecto, y cómo registrar un servicio realizado y un pago. Para tu trabajo, crea otro Core: empezará vacío.</p>');
  if(view==='accounts'){
    const accounts=state.quotes.filter(q=>['Aceptada','Cancelada'].includes(q.status));
    document.querySelectorAll('#content tbody tr').forEach((row,index)=>{
      if(accounts[index])row.cells[0].insertAdjacentHTML('beforeend',`<small>${esc(accounts[index].status)}</small>`);
    });
  }
};
$('#new-quote').onclick=()=>newQuote();

const originalCoreInput = updateCoreInput;
updateCoreInput = function(){
  originalCoreInput();
  const creating=$('#core-select').value==='new';
  const form=$('#login-form');
  form.querySelector('h1').textContent=creating?'Crea tu Core':'Tu espacio de trabajo';
  $('#core-select').closest('label').hidden=creating;
  form.elements.role.closest('label').hidden=creating;
  $('#create-core').hidden=creating;
  $('#create-core-note').hidden=!creating;
  $('#back-core').hidden=!creating||!Array.from($('#core-select').options).some(o=>o.value!=='new');
  form.querySelector('button:not([type])').textContent=creating?'Crear Core y entrar':'Abrir espacio →';
  if(creating)form.elements.role.value='admin';
};
$('#create-core').onclick=()=>{
  $('#core-select').value='new';updateCoreInput();$('#new-core-input').focus();
};
$('#back-core').onclick=()=>{
  $('#core-select').value=Array.from($('#core-select').options).find(o=>o.value!=='new')?.value||'new';
  updateCoreInput();
};
$('#core-select').addEventListener('change',updateCoreInput);
