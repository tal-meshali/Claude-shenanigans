function indAplicationOnload() {
    //    alert('2');
    init('idMainformI');
    getParmList();
    DisableDep();


}


var formx_1 = null;

function validateRecaptcha() {
    var ok = true;
//    var recpachax = document.getElementById("recaptcha_response_field");
//    if (recpachax != null) {
//        if (recpachax.value == null || recpachax.value == '') {
//            alert('Please enter what you see');
//            recpachax.focus();
//            ok = false;
//        }
//    }
//    else {
//        alert('Your capcha code did not load,please refresh the page');
//    }
//    return ok;

    var captcha_response = grecaptcha.getResponse();
    alert("captcha_response"+captcha_response);
    if (captcha_response.length == 0)
    {
        alert('Your capcha code did not load,please refresh the page');
        // Captcha is not Passed
        ok = false;
    }
    else
    {
        alert("true");
        // Captcha is Passed
        return ok;
    }
    return ok;
}

function validateApplicatnInfo() {
    var ok = true;

    if (formx_1.surname.value.trim() == "") {
        alert("Please Insert Your Family/Surname");
        formx_1.surname.focus();
        ok = false;
    }

    if (ok && formx_1.othernames.value.trim() == "") {
        alert("Please Insert Your Given/Other Names");
        formx_1.othernames.focus();
        ok = false;
    }

    if (ok && formx_1.title.value == '0X') {
        alert("Please Select Title");
        formx_1.title.focus();
        ok = false;
    }

    if (ok && formx_1.bdate.value == "") {
        alert("Please Insert Your Date of Birth");
        formx_1.bdate.focus();
        ok = false;
    }

    if (ok && formx_1.reenteredbdate.value == "") {
        alert("Please Insert Value For \'Re Enter Date of Birth\' Field");
        formx_1.reenteredbdate.focus();
        ok = false;
    }

    if (ok && formx_1.bdate.value != formx_1.reenteredbdate.value) {
        alert("Re selected birthday does not match with the previously selected date. Please check again");
        formx_1.reenteredbdate.focus();
        ok = false;
    }

    if (ok && formx_1.gender.value == "0X") {
        alert("Please Select Your Gender");
        formx_1.gender.focus();
        ok = false;
    }

    if (ok && formx_1.national.value == "0X") {
        alert("Please Select Your Nationality");
        formx_1.national.focus();
        ok = false;
    }

    // if (ok && formx_1.fromDeparture.value == "0X") {
    //     alert("Please Select Your Departure Country");
    //     formx_1.fromDeparture.focus();
    //     ok = false;
    // }
    // if (ok ) {
    //     alert(1);
    //     checkCOVIDRestrict(formx_1.national.value);
    // }
    //alert(formx_1.conbirth.value + '' + ok);
    if (ok && formx_1.conbirth.value == "0X") {
        alert("Please Select Your Country of Birth");
        formx_1.conbirth.focus();
        ok = false;
    }

    //passport issued date -----------------------------
    var hiddenPassOk = document.getElementById("idHiddenPassOk").value;
    if (ok && (formx_1.passportno.value.trim() == "" || hiddenPassOk == '0')) {
        alert("Please Insert a valid Passport Number");
        formx_1.passportno.focus();
        ok = false;
    }

    if (ok && (formx_1.reenteredpassportno.value.trim() == "")) {
        alert("Please Insert Value For \'Re Enter Passport Number\' Field");
        formx_1.reenteredpassportno.focus();
        ok = false;
    }

    if (ok && formx_1.passportno.value != formx_1.reenteredpassportno.value) {
        alert("Re-entered passport number does not match the previous entered passport number!");
        formx_1.passportno.focus();
        ok = false;
    }

    if (ok && formx_1.pidate.value == "") {
        alert("Please Insert Passport Issued Date");
        formx_1.pidate.focus();
        ok = false;
    }

    //passport Expiry date ------------------------
    if (ok && formx_1.pedate.value == "") {
        alert("Please Insert Passport Expiry Date");
        formx_1.pedate.focus();
        ok = false;
    }
    if(formx_1.appType.value == "7"){
     if (ok && formx_1.EntryType.value == "0X") {
        alert("Please Select Entry Type");
        formx_1.EntryType.focus();
        ok = false;
    }
    }
    return ok;
}

function validateChildInfo() {
    var ok = true;
    return ok;
}

function validateTravalInfo() {
    var ok = true;

    if (ok && formx_1.fromDeparture.value == "0X") {
        alert("Please Select Your Departure Country");
        formx_1.fromDeparture.focus();
        ok = false;
    }
    if (ok && formx_1.iadate.value == "") {
        alert("Please Insert Intended Arrival Date");
        formx_1.iadate.focus();
        ok = false;
    }

    if (ok && formx_1.puofvisit.value == '0X') {
        alert("Please Select Your Purpose of Visit");
        formx_1.puofvisit.focus();
        ok = false;
    }
    return ok;
}

function validateFinalDestination() {
    var ok = true;
    if (ok && formx_1.intdDates.value == 0) {
        alert("Please select number of intended dates");
        formx_1.intdDates.focus();
        ok = false;
    }
    if (ok && formx_1.fdest.value == 0) {
        alert("Please Insert Final Destination");
        formx_1.fdest.focus();
        ok = false;
    }
    return ok;
}

function validateRequestedVisaDays() {
    var ok = true;
    var form_value = formx_1.RequestedVisaDays.value;
    var goldenParadice = formx_1.goldenParadice.value;
   // alert("--|"+form_value+"|--"+formx_1.RequestedVisaDays.length+"--");
   // alert("type="+typeof(form_value));
    form_value = Number(form_value); 
   // alert("type="+typeof(form_value));
    
    if (isNaN(form_value)) {
        // alert("Please enter Requested Visa Days between 1-180.");
        alert("Please enter Requested Visa Days .");
        formx_1.RequestedVisaDays.focus();
        ok = false;
    } else if (form_value == "") {
        // alert("Please enter Requested Visa Days between 1-180..");
        alert("Please enter Requested Visa Days ..");
        formx_1.RequestedVisaDays.focus();
        ok = false;
    } else if (form_value < 1) {
        // alert("Please enter Requested Visa Days between 1-180...");
        alert("Please enter valid  Requested Visa Days...");
        formx_1.RequestedVisaDays.focus();
        ok = false;
    }else if (form_value > 180 && goldenParadice=="0") {
        // alert("Please enter Requested visa Days between 1-180");
        alert("Please enter valid Requested visa Days.");
        formx_1.RequestedVisaDays.focus();
        ok = false;
    }
    return ok;
}
function validateVaccinationStatus() {
    var ok = true;
    var form_value = formx_1.vaccinationFlag.value;


    if (form_value=="") {
        alert("Please enter Covid Vaccination Status.");
        formx_1.vaccinationFlag.focus();
        ok = false;
    }
    return ok;
}
function validateContactInfo() {
    var ok = true;
  
    if (formx_1.addone.value.trim() == "") {
        alert("Please Insert Address in Address Line 1");
        formx_1.addone.focus();
        ok = false;
    }
    else {
        var addyx = formx_1.addone.value.trim();
        if (addyx.length < 5) {
            alert("Please Insert valid Address for Address Line 1");
            formx_1.addone.focus();
            formx_1.addone.value = '';
            ok = false;
        }
    }

    /*if (formx_1.addtwo.value == "") {
            alert("Please Insert Street Name");
            formx_1.addtwo.focus();
            return false;
        }*/

    if (ok && formx_1.city.value.trim() == "") {
        alert("Please Insert Your City");
        formx_1.city.focus();
        ok = false;
    }

    if (ok && formx_1.state.value.trim() == "") {
        alert("Please Insert Your State");
        formx_1.state.focus();
        ok = false;
    }
    /*
        if(formx_1.zipcode.value==""){
            alert("Please Insert Your ZIP Code");
            formx_1.zipcode.focus();
            return false;
        }
*/
    if (ok && formx_1.adcountry.value == "0X") {
        alert("Please Select Your Country");
        formx_1.adcountry.focus();
        ok = false;
    }

    if (ok && formx_1.addinsl.value.trim() == "") {
        alert("Please Insert Address in Sri Lanka");
        formx_1.addinsl.focus();
        ok = false;
    }
    else {
        var addy = formx_1.addinsl.value.trim();

        if (addy.length < 5) {
            alert("Please Insert a valid  Address in Sri Lanka");
            formx_1.addinsl.focus();
            formx_1.addinsl.value = '';
            ok = false;
        }
    }
    if (ok && formx_1.email.value == "") {
        alert("Please Insert Contact Email");
        formx_1.email.focus();
        ok = false;
    }
    if (ok && formx_1.reenteremail.value == "") {
        alert("Please Insert Value For \'Re Enter Email Address\' Field");
        formx_1.reenteremail.focus();
        ok = false;
    }
    if (ok && formx_1.telephon.value == "") {
        alert("Please Insert Your Phone Number");
        formx_1.telephon.focus();
        ok = false;
    }
    return ok;
}

function validateFrmCompanyInfo() {
    var ok = true;
    if (ok && formx_1.frcomptelephon.value == "") {
        alert("Please Insert Your Phone Number");
        formx_1.frcomptelephon.focus();
        ok = false;
    }
    if (ok && formx_1.frcompemail.value == "") {
        alert("Please Insert Contact Email");
        formx_1.frcompemail.focus();
        ok = false;
    }
    if (ok && formx_1.frcompreenteredemail.value == "") {
        alert("Please Insert Value For \'Re Enter Email Address\' Field");
        formx_1.frcompreenteredemail.focus();
        ok = false;
    }
    return ok;
}

function validateSLCompanyInfo() {
    var ok = true;

    if (ok && formx_1.slcompname.value == "") {
        alert("Please Insert Company Name");
        formx_1.slcompname.focus();
        ok = false;
    }
    if (ok && formx_1.sladdone.value == "") {
        alert("Please Insert Company Address Line One");
        formx_1.sladdone.focus();
        ok = false;
    }
    else {
        var addyx = formx_1.sladdone.value.trim();

        if (ok && addyx.length < 5) {
            alert("Please Insert Company Address Line One");
            formx_1.sladdone.focus();
            formx_1.sladdone.value = '';
            ok = false;
        }
    }
    //    if (ok && formx_1.sladdtwo.value == "") {
    //        alert("Please Insert Company Address Line Two");
    //        formx_1.sladdtwo.focus();
    //        ok = false;
    //    }
    if (ok && formx_1.slcity.value == "") {
        alert("Please Insert City of Company");
        formx_1.slcity.focus();
        ok = false;
    }
    //       Commented on 2011-11-23 on request MALAWI AYYA
    //            if(formx_1.slstate.value==""){
    //            alert("Please Insert State of Company");
    //            formx_1.slstate.focus();
    //            return false;
    //        } 
    if (ok && formx_1.slcomptelephon.value == "") {
        alert("Please Insert Company Telephone Number");
        formx_1.slcomptelephon.focus();
        ok = false;
    }
    return ok;
}

function validateCharDec() {

}

function validateNoOfQuestionsChecked() {

    var hiddenQCodes = document.getElementsByName("hiddenQuestionCodes");
    var idStringY = "";
    var idStringN = "";
    var comN = null;
    var comY = null;
    var ok = true;
    var qCode = "";
    //    alert("1=="+hiddenQCodes.length);
    for (var i = 0;i < hiddenQCodes.length;i++) {
        qCode = hiddenQCodes[i].value;
        idStringN = "vlrN" + qCode;
        idStringY = "vlrY" + qCode;
        comN = document.getElementById(idStringN);
        comY = document.getElementById(idStringY);
        if (comN != null && !comN.checked && comY != null && !comY.checked) {
            alert('Please answer question ' + (i + 1) + ' before continuing');
            ok = false;
            comN.focus();
            //            alert(qCode);
            break;
        }
    }

    return ok;
}

function validateQuestions(object) {

    if (object.value != null && object.value == 1) {
        object.checked = false;
        alert('You are not eligible for visa');
    }

}

function valIndformone(button) {
    //alert("111111");

    //alert("apptype"+apptype);
    button.disabled = true;
    formx_1 = button.form;
    var ok = true;
    var xhiddenAppInfo = document.getElementById("hiddenAppInfo");
    var xhiddenDependentInfo = document.getElementById("hiddenDependentInfo");
    var xhiddenTrvlInfo = document.getElementById("hiddenTrvlInfo");
    var xhiddenContactInfo = document.getElementById("hiddenContactInfo");
    var xhiddenFrmCompany = document.getElementById("hiddenFrmCompany");
    var xhiddenSLCompany = document.getElementById("hiddenSLCompany");
    var xhiddenDestination = document.getElementById("hiddenDestination");
    var xhiddenCharDec = document.getElementById("hiddenCharDec");
    var xhiddenOthrDec = document.getElementById("hiddenOthrDec");
    var idHiddenrecapchaX = document.getElementById("idHiddenrecapcha");

    var xhiddenRequestedVisaDays = document.getElementById("hiddenRequestedVisaDays");
    var xhiddenVaccinationStatus = document.getElementById("hiddenVaccinationStatus");
    var entryType=document.getElementById("EntryType");
//    alert("222222");
    if (xhiddenAppInfo != null) {
        ok = validateApplicatnInfo();
    }
//    alert("1=" + ok);
    if (ok && xhiddenDependentInfo != null) {
        ok = validateChildInfo();
    }
//      alert("2=" + ok);

        //validating RequestedVisaDays(0-90)
    if (ok  && xhiddenTrvlInfo && xhiddenRequestedVisaDays != null) {
        ok = validateRequestedVisaDays();
    }
    //validating xhiddenVaccinationStatus
    if (ok  && xhiddenTrvlInfo && xhiddenVaccinationStatus != null) {
        ok = validateVaccinationStatus();
    }

    if (ok && xhiddenTrvlInfo != null) {
        ok = validateTravalInfo();
    }




    if (ok && xhiddenDestination != null) {
        ok = validateFinalDestination();
    }
//    alert("3=" + ok);
    if (ok && xhiddenContactInfo != null) {
        ok = validateContactInfo();
    }
//    alert("4=" + ok);
    if (ok && xhiddenFrmCompany != null) {
        ok = validateFrmCompanyInfo();
    }
//    alert("5=" + ok);
    if (ok && xhiddenSLCompany != null) {
        ok = validateSLCompanyInfo();
    }
//    alert("6=" + ok);
//    alert("7=" + ok);
    if (ok && xhiddenCharDec != null) {
        ok = validateCharDec();
    }
//    alert("8=" + ok);
    if (ok && xhiddenOthrDec != null) {
        ok = validateNoOfQuestionsChecked();
    }
//      alert("9=" + ok);
    var currentTime = new Date();
//    alert("currentTime"+currentTime);
    var month = currentTime.getMonth() + 1;
//    alert("month"+month);
    var day = currentTime.getDate();
//    alert("day"+day);
    var year = currentTime.getFullYear();
//    alert("year"+year);
    currentTime = month + "-" + day + "-" + year;
//    alert("currentTime"+currentTime);

    var curdate = Date.parse(currentTime);

//    alert(curdate);
    var bdate = Date.parse(formx_1.bdate.value);
    var pidate = Date.parse(formx_1.pidate.value);
    var pedate = Date.parse(formx_1.pedate.value);
    var iadate = Date.parse(formx_1.iadate.value);

    if (ok && (bdate > curdate)) {
        alert("Please Insert Valid Birth Date");
        formx_1.bdate.focus();
        ok = false;
    }

    if (ok && (pidate > curdate || pidate < bdate || pidate > iadate)) {
        alert("Please Insert Valid Passport Issued Date");
        formx_1.pidate.focus();
        ok = false;

    }
//    alert("10");
    if (ok && (pedate < curdate || pedate <= pidate || pedate < bdate || pedate < iadate)) {
        alert("Please Insert Valid Passport Expiry Date");
        formx_1.pedate.focus();
        ok = false;
    }

    if (ok && (iadate < curdate)) {
        alert("Please Insert Valid Intended Arrival Date");
        formx_1.iadate.focus();
        ok = false;
    }
//    if (ok && idHiddenrecapchaX != null) {
//        ok = validateRecaptcha();
//    }

    if (ok && formx_1.conf.checked == false) {
        alert("Please Confirm Your Information. \n Fraudulent transactions through on-line and off line channels shall be strictly prohibited and shall be considered as offenses.  True and correct information must be submitted at all times when submitting applications and making payments in order to avoid situations such as entry refusals , black listing of passport or other legal consequences.");
        //document.form1.conf.checked == true;
        ok = false;
    }
    if (ok) {
        //alert(ok);
//        button.disabled = true;
        stopCount();
        formx_1.submit();
    }else{
        button.disabled = false;
    }


}
// function checkCOVIDRestrict(nationality){
//     alert(2);
//     alert(nationality);
//     var val = nationality;
//
//     exCountryAJAXJS.validateCOVID(val, validCOVID);
//
// }

// function validCOVID(t) {
//     alert(3)
//     alert(t)
//     if(t=="Y"){
//         // alert("Prevailing situation arouse due to the Covid 19 outbreak, Please refrain applying for ETA  with the effect from 2020.03.14 ,00 00 hrs (Local time in Sri Lanka) until further notice.Any inconvenience caused in this regard is highly regretted.\n.");
//
//         if (confirm("Prevailing situation arouse due to the Covid 19 outbreak, please refrain applying for ETA. Further details please refer 'Home' page 'Emergency notification' section. Any inconvenience caused in this regard is highly regretted.")){
//             window.location.href="http://www.eta.gov.lk/slvisa/";
//             document.getElementById("submitButton").style.display='none';
//             document.getElementById("national").selectedIndex = 0;
//         }else{
//             document.getElementById("submitButton").style.display='none';
//             document.getElementById("national").selectedIndex = 0;
//         }
//
//     }
// }