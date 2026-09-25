var t;

function disableBackButton() {
    //    alert('dis');
    window.history.forward();
    if (history.length > 0) {
        history.go( + 1)
    }
//    t = setTimeout("disableBackButton()", 0); comment  by lakmal 2019-07095
}

function stopCount() {
    clearTimeout(t);

}

function parseDate(input,format) {
//alert('input '+input);
//alert('format '+format);
    format = format || 'yyyy-mm-dd';// default format
    var parts = input.match(/(\d+)/g), i = 0, fmt = {
    };
    // extract date-part indexes from the format
    format.replace(/(yyyy|dd|mm)/g, function (part) {
        fmt[part] = i++;
    });

    return new Date(parts[fmt['yyyy']], parts[fmt['mm']] - 1, parts[fmt['dd']]);
}

function countTextCharacter(field, cntfield, maxlimit) {
    //textCounter
    if (field.value.length > maxlimit)// if too long...trim it!
        field.value = field.value.substring(0, maxlimit);
    // otherwise, update 'characters left' counter
    else 
        cntfield.value = maxlimit - field.value.length;
}

function submittionOfForm3Group(button, valX) {
    //    alert('clicked'+valX);
    var messg = "Are you sure to confirm the details";
    if (valX != '3' || (valX == '3' && confirm(messg))) {
        //    alert(dependentDeletCount);
        document.getElementById("idActiontype").value = valX;
        button.disabled = true;
//        stopCount();
        button.form.submit();

    }

}

function submitform(button) {
//    stopCount();
    button.form.submit();

}

function submitformApp(button, formName) {

    document.getElementById("idAppType").value = button.id;
    if (document.getElementById("idAppSType") != null) {
        document.getElementById("idAppSType").value = '0';
    }
//    stopCount();

    var temp = button.id;
    //3,4,10,21,32,43,5,6,11,
    // if(temp=='3'||temp=='4'||temp=='10'||temp=='5'||temp=='6' ||temp=='11'){
    if(temp=='3'||temp=='4'||temp=='10'){
        alert(" Under the prevailing conditions of covid 19  please refrain applying from this category online.if you are applying for Business ETA please advice your local agent to contact the Immigration head office visa section for further instructions.Further Please note that two day in transit visas are not allowed at this stage under the health regulations but 12 hours air transit is available if your connecting flight is available within the time period.(For further instructions please refer the official website of civil aviation authority  https://www.caa.lk/en/  and official website of Srilanka tourism https://www.srilanka.travel/ )Please see the alert 9,10,11, and 12 for further information");
    }else {
        document.forms[formName].submit();
    }

}

function submitformPrint(formName) {
//    stopCount();
    document.forms[formName].submit();

}

function confirmForm(form) {
    var r = confirm("Are you sure to confirm the details ?");
    
    if (r) {
	var rx = confirm("Fraudulent transactions through on-line and off line channels shall be strictly prohibited and shall be considered as offenses.  True and correct information must be submitted at all times when submitting applications and making payments in order to avoid situations such as entry refusals , black listing of passport or other legal consequences.");
    if (rx) {
        submittionOfForm2Ind(form, '2');
    }
    }

}

function submittionOfForm2Ind(button, valX) {
    //    alert('clicked'+valX);
    button.disabled = true;
    document.getElementById("idActiontype").value = valX;
//    stopCount();
    button.form.submit();
}

function isCharacterKeyPress(evt) {
    var ok = false;
    var keyCode = (evt.which) ? evt.which : event.keyCode
    //    alert(keyCode);
    if (64 < keyCode && keyCode < 91) {
        ok = true;
    }
    //    alert(ok);
    return ok;

}

String.prototype.trim = function () {
    return this.replace(/^\s*/, "").replace(/\s*$/, "");
}

function convertToUpperCase(comp, check, event)///upperCase(x)
{
    //    alert(event);
    //    var ok=true;
    if (isCharacterKeyPress(event)) {
        //        alert('1');
        var y = comp.value;
        //        alert(y);
        for (var i = 0;i < y.length;i++) {
            var cha = y.charAt(i)
            var askyey = getAsciiVal(cha);
            //        alert(askyey);
            if (96 < askyey && askyey < 123) {
                //   clearText(comp); 
                comp.value = setCharAt(comp.value, i, cha.toUpperCase());

                //        }else{
            }
        }
    }
    //     alert('2');
    return event.keyCode;
    //    if (check == '1') {
    //        enabelDisableMember();
    //    }
    //    alert(y.toUpperCase());
}

function getAsciiVal(aChar) {
    //CalcKeyCode(aChar)
    var code = aChar.charCodeAt(0);
    return code;
}

function init(fomId) {
//    alert("init start");
    disableBackButton();
    //    if (!document.getElementById) {
    //        return false;
    //    }
    //    else {
    var f = document.getElementById(fomId);

    //    f.onselectstart = new Function("return false");
    f.oncontextmenu = new Function("return false");
    f.ondragdrop = new Function("return false");
    f.onpaste = new Function("return false");
    f.ondrop = new Function("return false");
    f.onCopy = new Function("return false");
    f.setAttribute("autocomplete", "off");

//    alert("init end");
    //    }
    //    f.on
}

function setCharAt(str, index, chr) {
    if (index > str.length - 1)
        return str;
    return str.substr(0, index) + chr + str.substr(index + 1);
}