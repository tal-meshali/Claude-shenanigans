var paramListJS = null;

function daysBetween(first, second) {

    // Copy date parts of the timestamps, discarding the time parts.
    // Do the math.
    var millisecondsPerDay = 1000 * 60 * 60 * 24;
    var millisBetween = first - second;
    var days = millisBetween / millisecondsPerDay;

    // Round down.
    return Math.floor(days);
}

function getParmList() {
    //    alert('heeeeeeeeeeeeeeeeeeeeeeeeee');
    paramListAJAXJS.getActivParameters(recieveParamList);
}

function recieveParamList(prm) {
    //    alert("prm=" + prm);
    paramListJS = prm;
    setMaxNoGroup();
}

function setMaxNoGroup() {

    for (var i = 0;paramListJS != null && i < paramListJS.length;i++) {
        //        alert(paramListJS[i].code);
        if ('GMEM' == paramListJS[i].code) {
            //            alert('ok eauqlll');
            maxNoOfMembers = paramListJS[i].value;
        }
        if ('MDEP' == paramListJS[i].code) {
            maxNoOfChildrenPerMember = paramListJS[i].value;
        }
    }
}

function checkDualCitizen(comp) {
    var selContry = comp.value.split('|')[0];
    //    alert(selContry);
    var code = 'DU' + selContry.trim();
    //    alert(code);
    for (var i = 0;paramListJS != null && i < paramListJS.length;i++) {
        //        alert(paramListJS[i].code);
        if (code == paramListJS[i].code) {
            //            alert('ok eauqlll');
            alert(paramListJS[i].message);
            break;
        }
    }

}

function checkMaxNo(code, compnt, value, type) {
    //        alert('code='+code +' /compnt='+ compnt +' /value ='+  value +' /type='+  type);
    var ok = true;
    for (var i = 0;paramListJS != null && i < paramListJS.length;i++) {
        if (code == paramListJS[i].code) {
            switch (type) {
                case 1:
                    if (value > paramListJS[i].value) {
                        alert(paramListJS[i].message);

                        if (paramListJS[i].restBox) {
                            compnt.value = '';
                             compnt.focus();
                        }
                        ok = false;
                       
                    }

                    break;
                case 2:
                    if (value < paramListJS[i].value) {
                        alert(paramListJS[i].message);
                        if (paramListJS[i].restBox) {
                            compnt.value = '';
                             compnt.focus();
                        }
                        ok = false;
                       
                    }
                    break;
                case 3:
                    if (value == paramListJS[i].value) {
                        alert(paramListJS[i].message);
                        if (paramListJS[i].restBox) {
                            compnt.value = '';
                             compnt.focus();
                        }
                        ok = false;
                     
                    }
                    break;
                default :

                    break;

            }

            break;
        }
    }
    return ok;
}