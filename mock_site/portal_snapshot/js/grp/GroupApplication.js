/* 
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */

function gropuAplicationOnload() {
    //    alert('2');
    init('idMainformC');
    getParmList();

}

function validateDestination() {
    var destination = document.getElementById("idDestination");
    var xIntendedStay = document.getElementById("idIntendedStay");

    var tempOk = true;
    if ((destination.value == null || destination.value == '' || destination.value.trim()=='')) {
        alert('Please fill your final destination');
        destination.focus();
        tempOk = false;
    }
    else {
        tempOk = validatealphanumWithSpace_onChange(destination, 'Final destination');
    }
    if (tempOk && (xIntendedStay.value == null || xIntendedStay.value == '' || xIntendedStay.value == '0X')) {
        alert('Please select your intended stay in days');
        xIntendedStay.focus();
        tempOk = false;
    }

    return tempOk;
}

function validateTravleInfo() {
    var xidArrivalDate = document.getElementById("idArrivalDate");
    var xidfromDeparture = document.getElementById("idfromDeparture");
    var xidPuofvisit = document.getElementById("idPuofvisit");
    var xidDepcity = document.getElementById("idDepcity");
    var xidAirline = document.getElementById("idAirline");
    var xidFlightno = document.getElementById("idFlightno");

    var tempOk = true;
    if (tempOk && (xidfromDeparture.value == null || xidfromDeparture.value == '' || xidfromDeparture.value == '0X')) {
        alert('Please select From Departure Country');
        xidfromDeparture.focus();
        tempOk = false;
    }
    if (tempOk) {
        if (xidArrivalDate.value == null || xidArrivalDate.value == '') {
            alert('Please Select your arrival date');
            tempOk = false;
            xidArrivalDate.focus();
        }
        else {
            var lDate = new Date();
            lDate.setDate(lDate.getDate() - 1);
            var FDate = parseDate(xidArrivalDate.value, 'mm/dd/yyyy');
            tempOk = validateDate(scwTargetEle, lDate, FDate, 'Intended arrival should be a future date');

        }
    }
    if (tempOk && (xidPuofvisit.value == null || xidPuofvisit.value == '' || xidPuofvisit.value == '0X')) {
        alert('Please select your purpose of visit');
        tempOk = false;
        xidPuofvisit.focus();
    }
    //        
    if (tempOk) {
        tempOk = validatealphanumWithSpace_onChange(xidDepcity, 'Port of departure');
    }

    if (tempOk) {
        tempOk = validatealphanumWithSpace_onChange(xidAirline, 'Airline / Vessel');
    }

    if (tempOk) {
        tempOk = validatealphanum_onChange(xidFlightno, 'Vessel / Flight Number');
    }
    //    alert('tempOk'+tempOk);
    return tempOk;
}

function validateContactInfo() {

    var xidContAddOne = document.getElementById("idContAddOne");
    var xidContAddTwo = document.getElementById("idContAddTwo");
    var xidContCity = document.getElementById("idContCity");
    var xidContState = document.getElementById("idContState");
    var xidContZipCode = document.getElementById("idContZipCode");
    var xidContPhoneNo = document.getElementById("idContPhoneNo");
    var xidContMobileno = document.getElementById("idContMobileno");
    var xidContFaxno = document.getElementById("idContFaxno");
    var xidContEmail = document.getElementById("idContEmail");
    var xidConCountry = document.getElementById("idConCountry");
    var xidContactAddSL = document.getElementById("idContactAddSL");
    var xidReEnterEmail = document.getElementById("idReEnterEmail");

    var tempOk = true;
    if (tempOk) {
        if ((xidContAddOne.value == null || xidContAddOne.value.trim() == '')) {
            alert('Please enter Address Line 1');
            tempOk = false;
            xidContAddOne.focus();
        }
        else {
            tempOk = validateCharacterAdrress_Onchange(xidContAddOne, 'Address Line 1');
        }
    }
    if (tempOk && (xidContAddTwo.value != null || xidContAddTwo.value != '')) {
        //        if (tempOk && (xidContAddTwo.value == null || xidContAddTwo.value == '')) {
        //            alert('Please enter contact address street');
        //            tempOk = false;
        //        }
        //        else {
        tempOk = validateCharacterAdrress_Onchange(xidContAddTwo, 'Address Line 2');
        //        }
    }
    if (tempOk) {

        //    alert('1 = '+tempOk) ;
        if (xidContCity.value == null || xidContCity.value.trim() == '') {
            alert('Please enter City');
            tempOk = false;
            xidContCity.focus();
        }
        else {
            tempOk = validatealphanumWithSpace_onChange(xidContCity, 'City');
        }
    }
    if (tempOk) {
        //    alert('2 = '+tempOk) ;
        if (xidContState.value == null || xidContState.value.trim() == '') {
            alert('Please enter State');
            tempOk = false;
            xidContState.focus();
        }
        else {
            tempOk = validatealphanumWithSpace_onChange(xidContState, 'State');

        }
    }

    if (tempOk && xidContZipCode.value != null && xidContZipCode.value != '') {
        tempOk = validatealphanum_onChange(xidContZipCode, 'Zip');

    }
    //   alert('3 = '+tempOk) ;
    if (tempOk && (xidConCountry.value == null || xidConCountry.value == '' || xidConCountry.value == '0X')) {
        alert('Please select Country');
        xidConCountry.focus();
        tempOk = false;
    }
    if (tempOk) {
        if (tempOk && (xidContPhoneNo.value == null || xidContPhoneNo.value == '')) {
            alert('Please  enter Telephone Number');
            tempOk = false;
            xidContPhoneNo.focus();
        }
        else {
            tempOk = validateContactNumber_onChange(xidContPhoneNo, 'Telephone Number');
        }
    }
    // alert('4 = '+tempOk) ;
    if (tempOk && xidContMobileno.value != '') {
        tempOk = validateContactNumber_onChange(xidContMobileno, 'Mobile Number');
    }
    if (tempOk && xidContFaxno.value != '') {
        tempOk = validateContactNumber_onChange(xidContFaxno, 'Fax Number');
    }

    if (tempOk) {
        if ((xidContEmail.value == null || xidContEmail.value == '')) {
            alert('Please enter Contact Email');
            tempOk = false;
            xidContEmail.focus();
        }
        else {
            tempOk = validateEmail(xidContEmail, 'Contact Email');
        }
    }

    if (tempOk && xidContactAddSL.value != '') {
        tempOk = validateCharacterAdrress_Onchange(xidContactAddSL, 'Address in Sri Lanka');
    }
    if (tempOk && xidReEnterEmail.value == "") {
        alert("Please Insert Value For \'Re Enter Email Address\' Field");
        xidReEnterEmail.focus();
        tempOk = false;
    }
    if (tempOk && xidReEnterEmail.value !== xidContEmail.value) {
        alert("Re-entered email does not match the previous entered email!");
        xidReEnterEmail.value = ''; // Clear the field
        xidReEnterEmail.focus();
        tempOk = false;
    }
    return tempOk;
}

function validateForeignCompanyInfo() {
    var xidFrCompName = document.getElementById("idFrCompName");
    var xidFrAddone = document.getElementById("idFrAddone");
    var xidFrAddtwo = document.getElementById("idFrAddtwo");
    var xidFrCity = document.getElementById("idFrCity");
    var xidFrState = document.getElementById("idFrState");
    var xidFrZipCodee = document.getElementById("idFrZipCodee");
    var xidFrCountry = document.getElementById("idFrCountry");
    var xidFrTelephon = document.getElementById("idFrTelephon");
    var xidFrMobileno = document.getElementById("idFrMobileno");
    var xidFrFaxno = document.getElementById("idFrFaxno");
    var xidfrCompEmail = document.getElementById("idFrCompEmail");
    var xidFrCompReEnteredEmail = document.getElementById("idFrCompReEnteredEmail");
    var tempOk = true;
    if (tempOk) {
        if (xidFrCompName.value == null || xidFrCompName.value == '') {
            alert('Please enter Company/Organisation Name');
            tempOk = false;
            xidFrCompName.focus();
        }
        else {
            tempOk = validatealphanumWithSpace_onChange(xidFrCompName, 'Company/Organisation Name');
        }
    }
    if (tempOk) {
        if (xidFrAddone.value == null || xidFrAddone.value == '') {
            alert('Please enter Address Line 1');
            tempOk = false;
            xidFrAddone.focus();
        }
        else {
            tempOk = validateCharacterAdrress_Onchange(xidFrAddone, 'Address Line 1');
        }
    }
    if (tempOk && (xidFrAddtwo.value == null || xidFrAddtwo.value == '')) {
        //alert(tempOk);
        //        if (tempOk && (xidFrAddtwo.value == null || xidFrAddtwo.value == '') && tempOk) {
        //            alert('Please enter company address street');
        //            tempOk = false;
        //        }
        //        else {
        tempOk = validateCharacterAdrress_Onchange(xidFrAddtwo, 'Address Line 2');
        //        }
    }
    //        
    //    alert('1='+tempOk) ;
    if (tempOk) {
        if ((xidFrCity.value == null || xidFrCity.value == '')) {
            alert('Please enter City');
            tempOk = false;
            xidFrCity.focus();
        }
        else {
            tempOk = validatealphanumWithSpace_onChange(xidFrCity, 'City');

        }
    }
    //    alert('2='+tempOk) ;
    if (tempOk) {
        //    alert('2 = '+tempOk) ;
        if (xidFrState.value == null || xidFrState.value == '') {
            alert('Please enter State');
            tempOk = false;
            xidFrState.focus();
        }
        else {
            tempOk = validatealphanumWithSpace_onChange(xidFrState, 'State');

        }
    }

    if (tempOk && xidFrZipCodee.value != null && xidFrZipCodee.value != '') {
        tempOk = validatealphanum_onChange(xidFrZipCodee, 'Zip');
    }
    if (tempOk && (xidFrCountry.value == null || xidFrCountry.value == '' || xidFrCountry.value == '0X')) {
        alert('Please select Country');
        xidFrCountry.focus();
        tempOk = false;
    }
    //   alert('3 = '+tempOk) ;
    if (tempOk) {
        if ((xidFrTelephon.value == null || xidFrTelephon.value == '')) {
            alert('Please enter Telephone Number');
            tempOk = false;
            xidFrTelephon.focus();
        }
        else {
            tempOk = validateContactNumber_onChange(xidFrTelephon, 'Telephone Number');
        }
    }
    // alert('4 = '+tempOk) ;
    if (tempOk && xidFrMobileno.value != '') {
        tempOk = validateContactNumber_onChange(xidFrMobileno, 'Mobile Number');
    }
    if (tempOk && xidFrFaxno.value != '') {
        tempOk = validateContactNumber_onChange(xidFrFaxno, 'Fax Number');
    }

    if (tempOk) {
        if ((xidfrCompEmail.value == null || xidfrCompEmail.value == '')) {
            alert('Please enter Contact Email');
            tempOk = false;
            xidfrCompEmail.focus();
        }
        else {
            tempOk = validateEmail(xidfrCompEmail, 'Contact Email');
        }
    }
    if (tempOk && xidFrCompReEnteredEmail.value == "") {
        alert("Please Insert Value For \'Re Enter Email Address\' Field");
        xidFrCompReEnteredEmail.focus();
        tempOk = false;
    }
    if (tempOk && xidFrCompReEnteredEmail.value !== xidfrCompEmail.value) {
        alert("Re-entered email does not match the previous entered email!");
        xidFrCompReEnteredEmail.value = ''; // Clear the field
        xidFrCompReEnteredEmail.focus();
        tempOk = false;
    }

    return tempOk;
}

function validateSLCompanyInfo() {

    var xidslCompName = document.getElementById("idslCompName");
    var xidSlAddOne = document.getElementById("idSlAddOne");
    var xidSlAddTwo = document.getElementById("idSlAddTwo");
    var xidSlCity = document.getElementById("idSlCity");
    var xidSlState = document.getElementById("idSlState");
    var xidSlZipCode = document.getElementById("idSlZipCode");
    var xidSlCompanyPhoneNo = document.getElementById("idSlCompanyPhoneNo");
    var xidSlCompanyMobileno = document.getElementById("idSlCompanyMobileno");
    var xidSlCompFaxno = document.getElementById("idSlCompFaxno");
    var xidSlCompEmail = document.getElementById("idSlCompEmail");

    var tempOk = true;
    // alert('1=' + tempOk)
    if (tempOk) {
        if (tempOk && (xidslCompName.value == null || xidslCompName.value == '')) {
            alert('Please enter Company/Organisation Name');
            tempOk = false;
            xidslCompName.focus();
        }
        else {
            tempOk = validatealphanumWithSpace_onChange(xidslCompName, 'Company/Organisation Name');
        }
    }
    // alert('2=' + tempOk)
    if (tempOk) {
        if ((xidSlAddOne.value == null || xidSlAddOne.value == '')) {
            alert('Please enter Address Line 1');
            tempOk = false;
            xidSlAddOne.focus();
        }
        else {
            tempOk = validateCharacterAdrress_Onchange(xidSlAddOne, 'Address Line 1');
        }
    }
    //  alert('3=' + tempOk)
    if (tempOk && (xidSlAddTwo.value == null || xidSlAddTwo.value == '')) {
        //alert(tempOk);
        //            if (tempOk && (xidSlAddTwo.value == null || xidSlAddTwo.value == '') && tempOk) {
        //                alert('Please enter the Sri Lankan company address line two');
        //                tempOk = false;
        //            }
        //            else {
        tempOk = validateCharacterAdrress_Onchange(xidSlAddTwo, 'Address Line 2');
        //            }
    }
    //  alert('4=' + tempOk)
    if (tempOk) {
        //        } if (tempOk){
        //    alert('1='+tempOk) ;
        if (tempOk && (xidSlCity.value == null || xidSlCity.value == '')) {
            alert('Please enter City');
            tempOk = false;
            xidSlCity.focus();
        }
        else {
            tempOk = validatealphanumWithSpace_onChange(xidSlCity, 'City');

        }
    }
    // alert('5=' + tempOk)
    //    alert('2='+tempOk) ; 
    if (tempOk) {
        // commented on 2011-11-23 on request MALAWI AYYA      
        // if (xidSlState.value != null && xidSlState.value != '') {
        //            tempOk = validatealphanumWithSpace_onChange(xidSlState, 'Sri Lankan company State');
        //
        //        }
        //        else {
        //            //    if (tempOk && xidSlState.value != null && xidSlState.value != '') {
        tempOk = validatealphanumWithSpace_onChange(xidSlState, 'State');

        //  }
    }
    // alert('6=' + tempOk)
    if (tempOk && xidSlZipCode.value != null && xidSlZipCode.value != '') {
        tempOk = validatealphanum_onChange(xidSlZipCode, 'Zip');

    }
    //  alert('7=' + tempOk)
    if (tempOk) {
        //   alert('3 = '+tempOk) ;
        if (xidSlCompanyPhoneNo.value == null || xidSlCompanyPhoneNo.value == '') {
            alert('Please enter Telephone Number');
            tempOk = false;
            xidSlCompanyPhoneNo.focus();
        }
        else {
            tempOk = validateContactNumber_onChange(xidSlCompanyPhoneNo, 'Telephone Number');
        }
    }
    //  alert('8=' + tempOk)
    // alert('4 = '+tempOk) ;
    if (tempOk && xidSlCompanyMobileno.value != '') {
        tempOk = validateContactNumber_onChange(xidSlCompanyMobileno, 'Mobile Number');
    }
    //  alert('9=' + tempOk)
    if (tempOk && xidSlCompFaxno.value != '') {
        tempOk = validateContactNumber_onChange(xidSlCompFaxno, 'Fax Number');
    }
    //  alert('10=' + tempOk)
    if (tempOk && xidSlCompEmail.value != '') {
        tempOk = validateEmail(xidSlCompEmail, 'Email');
    }
    // alert('11=' + tempOk)
    return tempOk;
}

function validateThirdParty() {
    var xidthirdPartyType = document.getElementById("idthirdPartyType");
    var xidthirdPartySName = document.getElementById("idthirdPartySName");
    var xidthirdPartyOName = document.getElementById("idthirdPartyOName");
    var xidthirdPartyAddOne = document.getElementById("idthirdPartyAddOne");
    var xidthirdPartyAddTwo = document.getElementById("idthirdPartyAddTwo");
    var xidthirdPartyCity = document.getElementById("idthirdPartyCity");
    var xidthirdPartyState = document.getElementById("idthirdPartyState");
    var xidThirdPartyCountry = document.getElementById("idThirdPartyCountry");
    var xidthirdPartyZipCode = document.getElementById("idthirdPartyZipCode");
    var xidthirdPartyMobileno = document.getElementById("idthirdPartyMobileno");
    var xidthirdPartyFaxno = document.getElementById("idthirdPartyFaxno");
    var xidThirdPartyPhoneNo = document.getElementById("idThirdPartyPhoneNo");
    var xidthirdPartyEmail = document.getElementById("idthirdPartyEmail");
    var xidthirdPartyReEnterEmail = document.getElementById("idThirdPartyReEnteredEmail");

    var tempOk = true;
    //alert('x1=' + tempOk);
    if (tempOk && (xidthirdPartyType.value == null || xidthirdPartyType.value == '' || xidthirdPartyType.value == '0X')) {
        alert('Please select Type of Third Party');
        xidthirdPartyType.focus();
        tempOk = false;
    }
    //  alert('x2=' + tempOk);
    if (tempOk) {
        if (xidthirdPartySName.value == null || xidthirdPartySName.value == '' || xidthirdPartySName.value.trim()=='') {
            alert('Please enter Surname/Family Name');
            xidthirdPartySName.focus();
            tempOk = false;
        }
        else {
            tempOk = validateName_OnChange(xidthirdPartySName, 'Surname/Family Name');
        }
    }
    //  alert('x3=' + tempOk);
    if (tempOk) {
        if (xidthirdPartyOName.value == null || xidthirdPartyOName.value == '' || xidthirdPartyOName.value.trim()=='') {
            alert('Please enter Other/Given names ');
            xidthirdPartyOName.focus();
            tempOk = false;
        }
        else {
            tempOk = validateName_OnChange(xidthirdPartyOName, 'Other/Given names');
        }
    }
    //  alert('x4=' + tempOk);
    if (tempOk) {
        if (xidthirdPartyAddOne.value == null || xidthirdPartyAddOne.value == '' || xidthirdPartyAddOne.value.trim()=='') {
            alert('Please enter Address Line 1');
            xidthirdPartyAddOne.focus();
            tempOk = false;
        }
        else {
            tempOk = validateCharacterAdrress_Onchange(xidthirdPartyAddOne, 'Address Line 1');
        }
    }
    //  alert('x5=' + tempOk);
    if (tempOk && (xidthirdPartyAddTwo.value == null || xidthirdPartyAddTwo.value == '')) {
        //alert(tempOk);
        //            if (tempOk && (xidthirdPartyAddTwo.value == null || xidthirdPartyAddTwo.value == '') && tempOk) {
        //                alert('Please enter third party Address street');
        //                tempOk = false;
        //            }
        //            else {
        tempOk = validateCharacterAdrress_Onchange(xidthirdPartyAddTwo, 'Address Line 2');
        //            }
    }
    //  alert('x6=' + tempOk);
    if (tempOk) {
        //        
        //    alert('1='+tempOk) ;
        if (xidthirdPartyCity.value == null || xidthirdPartyCity.value == '' || xidthirdPartyCity.value.trim()=='') {
            alert('Please enter City');
            xidthirdPartyCity.focus();
            tempOk = false;
        }
        else {
            tempOk = validatealphanumWithSpace_onChange(xidthirdPartyCity, 'City');

        }
    }
    // alert('x7=' + tempOk);
    if (tempOk) {
        if (xidthirdPartyState.value == null || xidthirdPartyState.value == '' || xidthirdPartyState.value.trim()=='') {
            alert('Please enter State');
            xidthirdPartyState.focus();
            tempOk = false;

        }
        else {
            //    if (tempOk && xidSlState.value != null && xidSlState.value != '') {
            tempOk = validatealphanumWithSpace_onChange(xidthirdPartyState, 'State');

        }
    }
    //alert('x8=' + tempOk);
    //    alert('2='+tempOk) ;
    if (tempOk && xidthirdPartyZipCode.value != null && xidthirdPartyZipCode.value != '') {
        tempOk = validatealphanum_onChange(xidthirdPartyZipCode, 'Zip');

    }
    if (tempOk && (xidThirdPartyCountry.value == null || xidThirdPartyCountry.value == '' || xidThirdPartyCountry.value == '0X')) {
        alert('Please select Country');
        xidThirdPartyCountry.focus();
        tempOk = false;
    }
    // alert('x9=' + tempOk);
    if (tempOk) {
        //   alert('3 = '+tempOk) ;
        if (xidThirdPartyPhoneNo.value == null || xidThirdPartyPhoneNo.value == '') {
            alert('Please enter Telephone Number');
            xidThirdPartyPhoneNo.focus();
            tempOk = false;
        }
        else {
            tempOk = validateContactNumber_onChange(xidThirdPartyPhoneNo, 'Telephone Number');

        }
    }
    //  alert('x10=' + tempOk);
    // alert('4 = '+tempOk) ;
    if (tempOk && xidthirdPartyMobileno.value != '') {
        tempOk = validateContactNumber_onChange(xidthirdPartyMobileno, 'Mobile number');
    }
    // alert('x11=' + tempOk);
    if (tempOk && xidthirdPartyFaxno.value != '') {
        tempOk = validateContactNumber_onChange(xidthirdPartyFaxno, 'Fax number');
    }
    // alert('x12=' + tempOk);

    if (tempOk) {
        if ((xidthirdPartyEmail.value == null || xidthirdPartyEmail.value == '')) {
            alert('Please enter Contact Email');
            tempOk = false;
            xidthirdPartyEmail.focus();
        }
        else {
            tempOk = validateEmail(xidthirdPartyEmail, 'Contact Email');
        }
    }

    if (tempOk) {
        if ((xidthirdPartyReEnterEmail.value == null || xidthirdPartyReEnterEmail.value == '')) {
            alert('Please Insert Value for \'Re Enter Email Field\'');
            tempOk = false;
            xidthirdPartyReEnterEmail.focus();
        }
        else {
            tempOk = validateEmail(xidthirdPartyReEnterEmail, 'Re Enter Contact Email');
        }
    }

    return tempOk;
}

function validateGroupMain(appType) {
    document.getElementById("idPassportNo").value = document.getElementById(("hiddenPassportNo" + id)).value;
    document.getElementById("idSurname").value = document.getElementById("hiddenSurname" + id).value;
    document.getElementById("idOthernames").value = document.getElementById("hiddenOtherNames" + id).value;
    document.getElementById("idTitle").value = document.getElementById("hiddenTitle" + id).value;
    document.getElementById("idNatinality").value = document.getElementById("hiddenNationality" + id).value;
    document.getElementById("idCOB").value = document.getElementById("hiddenCob" + id).value;
    document.getElementById("idOccupation").value = document.getElementById("hiddenOccupation" + id).value;
    document.getElementById("idRelationShip").value = document.getElementById("hiddenRealationShip" + id).value;
    document.getElementById("idGender").value = document.getElementById("hiddenGender" + id).value;
    document.getElementById("idDobYear").value = document.getElementById("hiddenDobYear" + id).value;
    document.getElementById("idDobMonth").value = document.getElementById("hiddenPassExMonth" + id).value;
    document.getElementById("idDobDate").value = document.getElementById("hiddenDobDate" + id).value;
    document.getElementById("idPassIsueYear").value = document.getElementById("hiddenPassIssuYear" + id).value;
    document.getElementById("idPassIsueMonth").value = document.getElementById("hiddenPassIssuMonth" + id).value;
    document.getElementById("idPassIsueDate").value = document.getElementById("hiddenPassIssueDate" + id).value;
    document.getElementById("idPassExpYear").value = document.getElementById("hiddenPassExYear" + id).value;
    document.getElementById("idPassExpMonth").value = document.getElementById("hiddenPassExMonth" + id).value;
    document.getElementById("idPassExpDate").value = document.getElementById("hiddenPassExDate" + id).value;
}

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
//    alert("captcha_response"+captcha_response);
    if (captcha_response.length == 0)
    {
//        alert("false");
        // Captcha is not Passed
        ok = false;
    }
    else
    {
//        alert("true");
        // Captcha is Passed
        return ok;
    }
    return ok;
}

function validateGroupForm1(button) {
    button.disabled = true;
    //    alert('ok vlidating====');
    var ok = true;

    var travleInfo = document.getElementById("hiddenTrvlInfo");
    var frignCompnyInfo = document.getElementById("hiddenFrmCompany");
    var slCompnyInfo = document.getElementById("hiddenSLCompany");
    var thirdPrtyInfo = document.getElementById("hiddenThirdParty");
    var contactInfo = document.getElementById("hiddenContactInfo");
    var destination = document.getElementById("idDestination");
    var idHiddenrecapchaX = document.getElementById("idHiddenrecapcha");
    var xhiddenRequestedVisaDays = document.getElementById("hiddenRequestedVisaDays");
    // alert(xhiddenRequestedVisaDays);
    if (ok && travleInfo != null) {
        //       alert('ok 1');
        ok = validateTravleInfo();

    }

    //   alert('1=' + ok);
    if (ok && destination != null) {
        //        alert('ok 2');
        ok = validateDestination();
    }
  //  alert('2=' + ok);
    if (ok && contactInfo != null) {
      //     alert('ok 3');
        ok = validateContactInfo();
    }
    //    alert('3=' + ok);
    if (ok && frignCompnyInfo != null) {
        //       alert('ok 4');
        ok = validateForeignCompanyInfo();
    }
    //    alert('4=' + ok);
    if (ok && slCompnyInfo != null) {
        //       alert('ok 5');
        ok = validateSLCompanyInfo();
        //           alert('7');
    }
    //    alert('5=' + ok);
    if (ok && thirdPrtyInfo != null) {
        //       alert('ok 6');
        ok = validateThirdParty();
        //  alert('7');
    }
//    if (ok && idHiddenrecapchaX != null) {
//        ok = validateRecaptcha();
//    }
    //validating RequestedVisaDays(0-90)
    if (ok  && xhiddenRequestedVisaDays != null) {
        // alert("11")
        ok = validateRequestedVisaDays();
    }

    if (ok) {
        var theContents = document.getElementById('idPuofvisit')[document.getElementById('idPuofvisit').selectedIndex].text;
        document.getElementById('idHiddenPOV').value = theContents.trim();
//        stopCount();
        button.form.submit();
    }
    else {
        button.disabled = false;
    }
}

function validateRequestedVisaDays() {
    var ok = true;
    var form_value = document.getElementById("RequestedVisaDays").value;
    // alert("--|"+form_value+"|----");
    // alert("type="+typeof(form_value));
    form_value = Number(form_value);
    // alert("type="+typeof(form_value));

    if (isNaN(form_value)) {
        alert("Please enter Requested Visa Days.");
        // alert("Please enter Requested Visa Days between 1-180.");
        document.getElementById("RequestedVisaDays").focus();
        ok = false;
    } else if (form_value == "") {
        alert("Please enter Requested Visa Days..");
        // alert("Please enter Requested Visa Days between 1-180..");
        document.getElementById("RequestedVisaDays").focus();
        ok = false;
    } else if (form_value < 1) {
        alert("Please enter valid Requested Visa Days...");
        // alert("Please enter Requested Visa Days between 1-180...");
        document.getElementById("RequestedVisaDays").focus();
        ok = false;
    } else if (form_value > 180) {
        alert("Please enter valid Requested visa Days");
        // alert("Please enter Requested visa Days between 1-180");
        document.getElementById("RequestedVisaDays").focus();
        ok = false;
    }
    return ok;
}