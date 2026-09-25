var comp = null;

function checkExemptedCountires(compt,appType) {

    comp = compt;
    var val = compt.value;
//    alert(val);
    var res = val.substring(0, 3); 
//    alert(val);

    if(res== 'NGA' || res== 'CMR' || res== 'CIV' ||res== 'GHA'){
    alert('You are kindly requested to apply ETA at Sri Lanka Overseas Missions or at the Head office of the Department of Immigration & Emigration, Colombo through Sri Lankan Sponsors. Failing to do so may cause for rejection of your ETA/Visa appeals.');
    }
    if(res=='PAK'){
        $('#myModal2').modal({
            backdrop: 'static'
        });
    }
    if((appType=='21'||appType=='32'||appType=='43')&&(res== 'CHN' || res== 'IDN' || res== 'MMR' ||res== 'PHL'||res== 'VNM')){
        $('#amberChannel').modal({
            backdrop: 'static'
        });
    }
    // Show or hide the 90 days option based on the country code - Maldives

    // Get the 90 days option element
    const nintyDaysOption = document.getElementById('nintydays');
    // const thirtyDaysOption = document.getElementById('thirtydays');

    if (res === 'MDV') {
        // Show 90 days option
        nintyDaysOption.style.display = '';
    } else {
        // Hide 90 days option
        nintyDaysOption.style.display = 'none';

        // If 90 days was selected, reset to default option
        const visaDaysSelect = document.getElementById('RequestedVisaDays');
        if (visaDaysSelect.value === '90') {
            visaDaysSelect.value = '0X';
            // Trigger change event if needed
            //below is commented business visa 90 days
            // visaDaysSelect.value = '30';
            visaDaysSelect.dispatchEvent(new Event('change'));
        }
    }

    //removed since 90 days visa options are not valid for business
    // var appType = document.getElementById('idAppType').value;

    // if (appType == '21') {
    //     var visaDaysSelect = document.getElementById("visaRequiredDaysRow");
    //
    //     if (res == 'MDV') {
    //         if (nintyDaysOption) {
    //             nintyDaysOption.style.display = '';
    //             visaDaysSelect.style.display = "table-row";
    //             thirtyDaysOption.style.display = '';
    //         }
    //     } else {
    //         if (nintyDaysOption) {
    //             nintyDaysOption.style.display = 'none';
    //             visaDaysSelect.style.display = "none";
    //             thirtyDaysOption.style.display = 'none';
    //             // var reqVisaDays = document.getElementById('RequestedVisaDays');
    //             // if (reqVisaDays) {
    //             //     reqVisaDays.value = '30';
    //             // }
    //         }
    //     }
    // }
    var indPass = document.getElementById('passportno');
    var grpPass = document.getElementById('idPassportNo');
    if (indPass != null) {
      //  document.getElementById('pidate').value = '';
     //   document.getElementById('pedate').value = '';
        indPass.value = '';
    }

    if (grpPass != null) {
       // document.getElementById('idPassIsueDate').value = '';
       // document.getElementById('idPassExpDate').value = '';
        grpPass.value = '';
    }

    exCountryAJAXJS.validateCountryExmpted(val, validCountry);

}

function validCountry(t) {
    if (t) {
        alert("You are welcome to Sri Lanka without ETA.");
        comp.value = '0X';
    }
}

function checkYellowFever(compt){
    comp = compt;
    var val = compt.value;
    
    exCountryAJAXJS.validateYellowFever(val, validYFCountry);
}

function validYFCountry(t) {
    if (t) {
        alert("YOU ARE HEREBY INFORMED TO SUBMIT YELLOW FEVER VACCINATION CERTIFICATE AT THE PORT OF ARRIVAL TO SRI LANKA IN ORDER TO COMPLY WITH INTERNATIONAL HEALTH REGULATIONS.");
    }
}


function checkCOVID(compt){
    comp = compt;
    var val = compt.value;

    exCountryAJAXJS.validateCOVID(val, validCOVID);

}

function validCOVID(t) {
    if (t=="T") {

        // alert("Prevailing situation has arisen due to the Covid 19 outbreak, Please refrain applying for ETA  for 14 days with the effect from 12.00pm (SL time) on 15th of March 2020. Any inconvenience in this regard  highly regretted.\n.");
        // alert("Prevailing situation arouse due to the Covid 19 outbreak, Please refrain applying for ETA  with the effect from 2020.03.15, 23 59 hrs (Local time in Sri Lanka) to 2020.03.29 , 24 00 hrs(Local time in Sri Lanka). Any inconvenience caused in this regard is highly regretted.\n.");
        alert("Prevailing situation has arisen due to the Covid 19 outbreak, We will hope to stop proceeding ETA within next 24 hours.");
        document.getElementById("submitButton").style.display='none';
        document.getElementById("fromDeparture").selectedIndex = 0;
    }else if(t=="Y"){
        // alert("Prevailing situation arouse due to the Covid 19 outbreak, Please refrain applying for ETA  with the effect from 2020.03.14 ,00 00 hrs (Local time in Sri Lanka) until further notice.Any inconvenience caused in this regard is highly regretted.\n.");

        // if (confirm("Prevailing situation arouse due to the Covid 19 outbreak, please refrain applying for ETA. Further details please refer 'Home' page 'Emergency notification' section. Any inconvenience caused in this regard is highly regretted.")){
        if (confirm("Please refrain applying for ETA according to prevailing situation arouse due to the Covid 19 outbreak. Please contact Visa Division of the Department of Immigration and Emigration, Sri Lanka for further details. Any inconvenience caused in this regard is highly regretted.")){
            window.location.href="http://www.eta.gov.lk/slvisa/";
            document.getElementById("submitButton").style.display='none';
            document.getElementById("fromDeparture").selectedIndex = 0;
        }else{
            document.getElementById("submitButton").style.display='none';
            document.getElementById("fromDeparture").selectedIndex = 0;
        }

    }else{
        // alert("Prevailing situation has arisen due to the Covid 19 outbreak, please proceed  to apply ETA if your travel is essential only. ")
        document.getElementById("submitButton").style.display='block';

    }
}

function checkCOVIDGroup(compt){
    comp = compt;
    var val = compt.value;
    exCountryAJAXJS.validateCOVID(val, validCOVIDGroup);

}

function validCOVIDGroup(t) {

    if (t=="T") {

        // alert("Prevailing situation has arisen due to the Covid 19 outbreak, Please refrain applying for ETA  for 14 days with the effect from 12.00pm (SL time) on 15th of March 2020. Any inconvenience in this regard  highly regretted.\n.");
        // alert("Prevailing situation arouse due to the Covid 19 outbreak, Please refrain applying for ETA  with the effect from 2020.03.15, 23 59 hrs (Local time in Sri Lanka) to 2020.03.29 , 24 00 hrs(Local time in Sri Lanka). Any inconvenience caused in this regard is highly regretted.\n.");
        alert("Prevailing situation has arisen due to the Covid 19 outbreak, We will hope to stop proceeding ETA within next 24 hours.");
        // document.getElementById("idAddMember").style.display='none';
        document.getElementById("idfromDeparture").selectedIndex = 0;
    }else if(t=="Y"){
        // alert("Prevailing situation arouse due to the Covid 19 outbreak, Please refrain applying for ETA  with the effect from 2020.03.14 ,00 00 hrs (Local time in Sri Lanka) until further notice.Any inconvenience caused in this regard is highly regretted.\n.");
        if (confirm("Prevailing situation arouse due to the Covid 19 outbreak, please refrain applying for ETA. Further details please refer 'Home' page 'Emergency notification' section. Any inconvenience caused in this regard is highly regretted.")){
            window.location.href="http://www.eta.gov.lk/slvisa/";
            // document.getElementById("idAddMember").style.display='none';
            document.getElementById("idfromDeparture").selectedIndex = 0;
        }else{

            // document.getElementById("idAddMember").style.display='none';
            document.getElementById("idfromDeparture").selectedIndex = 0;
        }
    }else{
        // alert("Prevailing situation has arisen due to the Covid 19 outbreak, please proceed  to apply ETA if your travel is essential only. ")
        // document.getElementById("idAddMember").style.display='block';

    }
}