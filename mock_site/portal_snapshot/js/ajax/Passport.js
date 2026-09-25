function validatePassPortJS(comp) {
    document.getElementById('idLodingPassPort').innerHTML = '';
    var passPortNo = comp.value.trim().toUpperCase();
    var ok = validatealphanum_onChange(comp, 'Passport Number');
    //      alert('passPortNo='+passPortNo);
    if (ok) {
        var con = document.getElementById('idNatinality').value.trim().toUpperCase();
        var chekSt = passPortNo + con;
        document.getElementById('idLodingPassPort').innerHTML = "<img height='32' width='32'' src='images/process.gif'/>";
        if (con != '0X') {
            if (passPortNo != null && passPortNo != '' && checkDuplicatePassportXY(chekSt)) {
                //    alert('comp=='+passPortNo);
                ajaxValidate.validatePassPort(passPortNo, con, gotPassPortNO);
            }
            else {
                comp.value = '';
                document.getElementById('idLodingPassPort').innerHTML = '';
            }
        }
        else {
            alert('Please select country of nationality first');
            comp.value = '';
            document.getElementById('idLodingPassPort').innerHTML = '';
        }
    }
}

// function validateTouristnoJSInd(comp) {
//     document.getElementById('idLodingtouristno').innerHTML = '';
//     var touristno = comp.value.trim().toUpperCase();
//        // alert('1'+touristno);
//     // var ok = validatealphanum_onChange(comp, 'Tourist registered No');
//        // alert('2=='+ok);
//     // if (ok) {
//         document.getElementById('idLodingtouristno').innerHTML = "<img height='32' width='32'' src='images/process.gif'/>";
//
//             if (touristno != null && touristno != '') {
//                 //    alert('comp=='+passPortNo);
//                 ajaxValidate.validateTouristno(touristno,gotTouristnoIndividual);
//             }
//             else {
//                 comp.value = '';
//                 document.getElementById('idLodingtouristno').innerHTML = '';
//             }
//     // }
// }
//
// function gotTouristnoIndividual(t) {
//     if (t != null) {
//         alert(t);
//         document.getElementById('idLodingtouristno').innerHTML = '';
//         document.getElementById('touristno').value = '';
//     }
//     else {
//         document.getElementById('idLodingtouristno').innerHTML = '';
//         document.getElementById('idHiddentouristnoOk').value = '1';
//         var valP = document.getElementById('touristno').value;
//         document.getElementById('touristno').value = valP.toUpperCase();
//     }
//
// }
function validatePassPortJSInd(comp) {
    document.getElementById('idLodingPassPort').innerHTML = '';
    var passPortNo = comp.value.trim().toUpperCase();
       // alert('1'+passPortNo);
    var ok = validatealphanum_onChange(comp, 'Passport Number');
       // alert('2=='+ok);
       //   alert('passPortNo='+passPortNo);
    if (ok) {
        var coa = document.getElementById('national').value.split('|')[0];

        document.getElementById('idLodingPassPort').innerHTML = "<img height='32' width='32'' src='images/process.gif'/>";
        if (coa != '0X') {
            if (passPortNo != null && passPortNo != '') {
                   // alert('comp=='+passPortNo);
                ajaxValidate.validateIndPassport(passPortNo, coa, gotPassPortNOIndividual);
            }
            else {
                comp.value = '';
                document.getElementById('idLodingPassPort').innerHTML = '';
            }
        }
        else {
            alert('Please select country of nationality first');
            comp.value = '';
            document.getElementById('idLodingPassPort').innerHTML = '';
        }
    }
}
function validateReEnteredPPNo(obj, passportNoFieldId) {
    var passportNo = document.getElementById(passportNoFieldId).value; // Get first entered passport number value
    var reEnterPassportNo = obj.value; // Get re-entered passport number value
    var ok = true; // Default to true


    if (reEnterPassportNo !== '') {
        reEnterPassportNo = reEnterPassportNo.toUpperCase();
        obj.value = reEnterPassportNo;
        if (reEnterPassportNo !== passportNo) {
            alert("Re-entered passport number does not match the previous entered passport number!");
            obj.value = ''; // Clear the field
            obj.focus(); // Focus back to re-enter passport number field
            ok = false;
        }
    }
}

function gotPassPortNO(t) {
    if (t != null) {
        alert(t);
        document.getElementById('idLodingPassPort').innerHTML = '';
        document.getElementById('idPassportNo').value = '';
    }
    else {
        document.getElementById('idLodingPassPort').innerHTML = '';
        document.getElementById('idHiddenPassOk').value = '1';
        var valP = document.getElementById('idPassportNo').value;
        document.getElementById('idPassportNo').value = valP.toUpperCase();
    }

}

function gotPassPortNOIndividual(t) {
    // alert("done");
    if (t != null) {
        alert(t);
        document.getElementById('idLodingPassPort').innerHTML = '';
        document.getElementById('passportno').value = '';
    }
    else {
        document.getElementById('idLodingPassPort').innerHTML = '';
        document.getElementById('idHiddenPassOk').value = '1';
        var valP = document.getElementById('passportno').value;
        document.getElementById('passportno').value = valP.toUpperCase();
    }

}

function validateDateDiff(comp) {
    var arrival = document.getElementById('idHiddenArrivalDate').value;
    //var arrival= document.getElementById('idHiddenArrivalDate').value;
    //    var date1=comp.value;
    var date1T = Date.parse(comp.value);
    var arrivalT = Date.parse(arrival);
    var id = comp.id;
    var ok = true;
    if (arrival == null || arrival == '') {
        alert("Arrival date not found");
        comp.value = "";
        ok = false;
    }
    if (id == 'idPassIsueDate') {
        if (date1T == null || date1T == '') {
            alert("Please select a passport issued date");
            comp.value = "";
            ok = false;
        }
        if (date1T > arrivalT) {
            alert("Passport issued date should be prior to the arrival date");
            comp.value = "";
            ok = false;
        }
    }
    if (id == 'idPassExpDate') {
        if (date1T == null || date1T == '') {
            alert("Please select a passport expiry date");
            comp.value = "";
            ok = false;
        }
        if (date1T < arrivalT) {
            alert("Passport expiry date should be later to the arrival date");
            comp.value = "";
            ok = false;
        }
        if (date1T < arrivalT && ok) {
            alert("Passport expiry date should be later to the arrival date");
            comp.value = "";
            ok = false;
        }
    }

    return ok

}

function checkDuplicatePassportXY(chst) {
    //alert('dup=' +passsNo);
    var selPassPort = document.getElementsByName("hiddenPassportNo");
    var con = document.getElementsByName('hiddenNationality');
    //   alert('dup=' +selPassPort);
    // selPackage.options.length = 0;// clear all options
    var ok = true;
    for (var i = 0;selPassPort != null && i < selPassPort.length;i++) {
        //         alert('checking value===' + selPassPort[i].value.trim());
        var checkPs = selPassPort[i].value.trim() + con[i].value.trim();
        if (checkPs == chst) {
            alert('Duplicate passport found,cannot add');
            ok = false;
            break;
        }
    }
    //    alert(ok);
    return ok;
}