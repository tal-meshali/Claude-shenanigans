/* 
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */

var dependentCount = 0;
var dependentDeletCount = 0
var maxNoOfChildrenPerMember = 0;

function initializeDependentCounts(count) {
    //    alert(count);
    dependentCount = count;
    dependentDeletCount = count;
    if (count > 0) {
        setDependentDeatilsHeader();
    }
}

function addDependentMemberX(appType) {
    if (dependentDeletCount < maxNoOfChildrenPerMember) {
        var dSurname = document.getElementById("idDSurname");
        var dOtherNames = document.getElementById("idDOthernames");
        var dRealationShip = document.getElementById("idDRelationship");
        var dGender = document.getElementById("idDGender");
        var dDobStamp = document.getElementById("idDDobDate");
        var idReEnteredDDobDate = document.getElementById("idReEnteredDDobDate");
        var passportNo = document.getElementById("idPassportNo").value.trim();
        var natinality = document.getElementById("idNatinality").value.trim();
        var dGenderString = "";
        var tempOk = true;

        if (tempOk && (dSurname.value == null || dSurname.value == '' || dSurname.value.trim()=='')) {
            alert(' Please enter Surname/Family Name');
            dSurname.focus();
            tempOk = false;
        }
        else {
            ok = validateName_OnChange(dSurname, 'Surname/Family Name');

        }

        if (tempOk) {
            if ((dOtherNames.value == null || dOtherNames.value == '' || dOtherNames.value.trim()=='')) {
                tempOk = false;
                alert('Please enter Other/Given Names ');
                dOtherNames.focus();
            }
            else {
                ok = validateName_OnChange(dOtherNames, 'Other/Given Names ');

            }
        }
        //    alert('1');
        if (tempOk && (dDobStamp.value == null || dDobStamp.value == '')) {
            tempOk = false;
            alert('Please select Date of Birth');
            dDobStamp.focus();
        }

        if (tempOk && (idReEnteredDDobDate.value == null ||idReEnteredDDobDate.value == '')) {
            alert("Please Insert Re-entered Date of Birth of Child");
            document.getElementById('idReEnteredDDobDate').focus();
            tempOk = false;
        }
        if (tempOk && idReEnteredDDobDate.value !== dDobStamp.value) {
            alert("Re-entered Date of Birth does not match the previous entered Date of Birth!");
            document.getElementById('idReEnteredDDobDate').focus();
            tempOk = false;
        }
        //    alert('2');
        if (tempOk) {
            if (dGender.value == null || dGender.value == '0X') {
                tempOk = false;
                alert('Please select Gender');
                dGender.focus();
            }
            else {
                var theContents = document.getElementById('idDGender')[document.getElementById('idDGender').selectedIndex].text;
                dGenderString = theContents.trim();
            }
        }
        if (tempOk && (passportNo == null || passportNo == '')) {
            alert('Please enter passport number of the Group memeber.');
            document.getElementById("idPassportNo").focus();
            tempOk = false;
        }

        if (tempOk && (dRealationShip.value == null || dRealationShip.value == '0X')) {
            tempOk = false;
            alert('Please select Relationship');
            dRealationShip.focus();
        }

        if (tempOk) {
            dependentCount++;
            dependentDeletCount++;
            var memberStr = "";

            if (dependentDeletCount == 1) {
                setDependentDeatilsHeader();
            }
            memberStr = "<div id='idDependentDiv" + dependentCount + "'><table width='562' border='0' cellpadding='0' cellspacing='5' style='table-layout:fixed'><input name='thiddenDMgenderString' id='thiddengenderString" + memberCount + "' type='hidden' value='" + dGenderString + "' /><input name='thiddenDNationality' id='thiddenDNationality" + dependentCount + "' type='hidden' value='" + natinality + "' /><input name='thiddenDPassportNo' id='thiddenDPassportNo" + dependentCount + "' type='hidden' value='" + passportNo + "' /><input name='thiddenDSurname' id='thiddenDSurname" + dependentCount + "' type='hidden' value='" + dSurname.value + "' /><input name='thiddenDOtherNames'  id='thiddenDOtherNames" + dependentCount + "' type='hidden' value='" + dOtherNames.value + "' /><input name='thiddenDRealationShip' id='thiddenDRealationShip" + dependentCount + "' type='hidden' value='" + dRealationShip.value + "' /><input name='thiddenDGender' id='thiddenDGender" + dependentCount + "' type='hidden' value='" + dGender.value + "' /><input name='thiddenDDobDate' id='thiddenDDobDate" + dependentCount + "' type='hidden' value='" + dDobStamp.value + "'/><col width='100'> <col width='200'> <col width='80'><col width='80'> <col width='51'> <col width='51'><tr align='left' valign='middle' class='inner_text_1'><td width='100' height='25'>" + passportNo + "</td><td width='200' height='25'>" + dSurname.value + "</td><td width='80' height='25'>" + dDobStamp.value + "</td> <td width='80' height='25'>" + dGenderString + "</td><td width='51' height='25'><a href='#' id='" + dependentCount + "' onclick='editDependent(this.id);'>Edit</a></td> <td width='51' height='25'><a href='#' onclick='deleteDependent(this.id);' id='" + dependentCount + "'/>Remove</a></td></tr></table></div>";
            // alert(memberStr);
            document.getElementById('idDependentDiv0').innerHTML += memberStr;

            if (dependentDeletCount == maxNoOfChildrenPerMember) {
                alert('You have reached the maximum number of children per applicant,you wont be able to add more after this');
            }
            resetFieldsD();
        }

    }
    else {
        alert('You have reached the maximum number of children per applicant,you cannot add more');
        resetFieldsD();
    }

}

function deleteDependent(id) {
    var messg = "Are you sure to delete this child details??";
    //    alert(dependentDeletCount);
    if (confirm(messg)) {
        dependentDeletCount--;
        var tem = '';
        //        var tem = "idDependentDiv" + id;
        if (dependentDeletCount == 0) {
            document.getElementById('idDependentDiv0').innerHTML = '';
            document.getElementById('idDepHedDiv').innerHTML = '';
        }
        else {
            var tem = "idDependentDiv" + id;
            document.getElementById(tem).innerHTML = '';
        }

        // alert(tem);
    }
}

function deleteDependentCount() {
    dependentDeletCount--;

}

function resetFieldsD() {
    //    document.getElementById("idDDependentOFf").value = '0X';
    document.getElementById("idDSurname").value = '';
    document.getElementById("idDOthernames").value = '';
    document.getElementById("idDGender").value = '0X';
    document.getElementById("idDDobDate").value = '';
    document.getElementById("idDRelationship").value = '0X';
    document.getElementById("idHiddenDepEdit").value = '0';
    document.getElementById("idReEnteredDDobDate").value = '';
}

function editDependent(id) {
    //    var tem="idMembersDiv"+id;
    //    var idPass="idPassportNo"+id;
    //    alert(document.getElementById(idPass).value);
    //    document.getElementById("idDDependentOFf").value = document.getElementById(("hiddenDPassportNo" + id)).value;
    var editD = document.getElementById("idHiddenDepEdit").value;
    var editMessage = 'There is a member detail not yet saved,do you want to discard this details?';
    if (editD == '0' || (ok > 0 && confirm(editMessage))) {
        document.getElementById("idHiddenDepEdit").value = id;
        document.getElementById("idDSurname").value = document.getElementById("thiddenDSurname" + id).value;
        document.getElementById("idDOthernames").value = document.getElementById("thiddenDOtherNames" + id).value;
        document.getElementById("idDGender").value = document.getElementById("thiddenDGender" + id).value;
        document.getElementById("idDDobDate").value = document.getElementById("thiddenDDobDate" + id).value;
        document.getElementById("idReEnteredDDobDate").value = document.getElementById("thiddenDDobDate" + id).value;
        document.getElementById("idDRelationship").value = document.getElementById("thiddenDRealationShip" + id).value;

        document.getElementById('idEnableDepInfo').checked = true;
        document.getElementById("idDSurname").disabled = false;
        document.getElementById("idDOthernames").disabled = false;
        document.getElementById("idDRelationship").disabled = false;
        document.getElementById("idDGender").disabled = false;
        document.getElementById("idDDobDate").disabled = false;
        document.getElementById("idReEnteredDDobDate").disabled = false;
        document.getElementById("idAddDependent").disabled = false;

        var tem = "idDependentDiv" + id;
        document.getElementById(tem).innerHTML = '';
        dependentDeletCount--;
        if (dependentDeletCount == 0) {
            //        tem = "idDependentDiv0";
            document.getElementById('idDependentDiv0').innerHTML = '';
            document.getElementById('idDepHedDiv').innerHTML = '';
        }
    }
}

function setDependentDeatilsHeader() {

    var str = "<table height='30' border='0' cellpadding='0' cellspacing='5' width='562' style='table-layout:fixed'><col width='100'> <col width='200'> <col width='80'><col width='80'> <col width='51'> <col width='51'><tr align='center' valign='middle' class='textHeadingBlack'><td width='100' height='30' class='TBline_2'>Passport No</td> <td width='200' height='30' class='TBline_2'>Surname</td> <td width='80' height='30' class='TBline_2'>Date of Birth</td> <td width='80' height='30' class='TBline_2'>Gender</td> <td width='51' height='30' class='TBline_2'>Edit</td> <td width='51' height='30' class='TBline_2'>Remove</td></tr></table>";
    document.getElementById('idDepHedDiv').innerHTML = str;

}

function checkAllManFiled() {

    var passportNo = document.getElementById("idPassportNo").value;
    //    alert("1=" + passportNo);'    
    var hiddenPassOk = document.getElementById("idHiddenPassOk").value;
    //    alert("2=" + hiddenPassOk);
    var surname = document.getElementById("idSurname").value;
    //    alert("3=" + surname);
    var otherNames = document.getElementById("idOthernames").value;
    //    alert("4=" + otherNames);
    var title = document.getElementById("idTitle").value;
    //    alert("5=" + title);
    var nationality = document.getElementById("idNatinality").value;
    //    alert("6=" + nationality);
    var cob = document.getElementById("idCOB").value;
    //    alert("7=" + cob);
    var coa = document.getElementById("idCOA").value;
    //    alert("8=" + coa);
    //    var realationShip = document.getElementById("idRelationShip");
    var gender = document.getElementById("idGender").value;
    //    alert("9=" + gender);
    var dobStamp = document.getElementById("idDobDate").value;
    //    alert("10=" + dobStamp);
    var passIssuStamp = document.getElementById("idPassIsueDate").value;
    //    alert("11=" + passIssuStamp);
    var passExStamp = document.getElementById("idPassExpDate").value;
    //    alert("12=" + passExStamp);
    var ok = false;

    if (passportNo != null && passportNo != '' && hiddenPassOk != '0' && surname != null && surname != '' && otherNames != null && otherNames != '' && title != null && title != '0X' && nationality != null && nationality != '0X' && cob != null && cob != '0X' && coa != null && coa != '0X' && gender != null && gender != '0X' && dobStamp != null && dobStamp != '' && passIssuStamp != null && passIssuStamp != '' && passExStamp != null && passExStamp != '') {
        ok = true;
    }
    else {
        ok = false;
        alert('Please fill in member details first');
    }

    return ok;
}

function enabelDisableDependent(ch) {

    if (ch == 1 && checkAllManFiled() && document.getElementById('idEnableDepInfo').checked) {
        document.getElementById("idDSurname").disabled = false;
        document.getElementById("idDOthernames").disabled = false;
        document.getElementById("idDRelationship").disabled = false;
        document.getElementById("idDGender").disabled = false;
        document.getElementById("idDDobDate").disabled = false;
        document.getElementById("idAddDependent").disabled = false;
        document.getElementById("idReEnteredDDobDate").disabled = false;
    }
    else {
        document.getElementById('idEnableDepInfo').checked = false;
        document.getElementById("idDSurname").disabled = true;
        document.getElementById("idDOthernames").disabled = true;
        document.getElementById("idDRelationship").disabled = true;
        document.getElementById("idDGender").disabled = true;
        document.getElementById("idDDobDate").disabled = true;
        document.getElementById("idAddDependent").disabled = true;
        document.getElementById("idReEnteredDDobDate").disabled = true;
        this.resetFieldsD();
    }

}

function getActualDependenString() {
    var reSt = '';
    var thiddenDMgenderStringX = document.getElementsByName('thiddenDMgenderString');
    var hiddenDPassportNoX = document.getElementById('idPassportNo');
    var hiddenDSurnameX = document.getElementsByName('thiddenDSurname');
    var hiddenDOtherNamesX = document.getElementsByName('thiddenDOtherNames');
    var hiddenDRealationShipX = document.getElementsByName('thiddenDRealationShip');
    var hiddenDGenderX = document.getElementsByName('thiddenDGender');
    var hiddenDDobDateX = document.getElementsByName('thiddenDDobDate');

    for (var i = 0;i < dependentDeletCount;i++) {
        var t = i + 1;
        var tm = "<div id='mx" + memberCount + "'><div id='idDependentDiv" + t + "'><table width='562' border='0' cellpadding='0' cellspacing='5' style='table-layout:fixed'><input name='hiddenDMemberNo' id='hiddenDMemberNo" + t + "' type='hidden' value='" + memberCount + "' /><input name='hiddenDMgenderString' id='hiddengenderString" + t + "' type='hidden' value='" + thiddenDMgenderStringX[i].value + "' /><input name='hiddenDPassportNo' id='hiddenDPassportNo" + t + "' type='hidden' value='" + hiddenDPassportNoX.value + "' /><input name='hiddenDSurname' id='hiddenDSurname" + t + "' type='hidden' value='" + hiddenDSurnameX[i].value + "' /><input name='hiddenDOtherNames'  id='hiddenDOtherNames" + t + "' type='hidden' value='" + hiddenDOtherNamesX[i].value + "' /><input name='hiddenDRealationShip' id='hiddenDRealationShip" + t + "' type='hidden' value='" + hiddenDRealationShipX[i].value + "' /><input name='hiddenDGender' id='hiddenDGender" + t + "' type='hidden' value='" + hiddenDGenderX[i].value + "' /><input name='hiddenDDobDate' id='hiddenDDobDate" + t + "' type='hidden' value='" + hiddenDDobDateX[i].value + "'/><col width=50> <col width='80'> <col width='130'><col width='80'> <col width='80'> <col width='80'><col width='31'> <col width='31'> <tr align='left' valign='middle' class='inner_text_1'><td width='50' height='25'>Child</td><td width='80' height='25'>" + hiddenDPassportNoX.value + "</td><td width='130' height='25'>" + hiddenDSurnameX[i].value + "</td><td width='80' height='25'>" + hiddenDDobDateX[i].value + "</td> <td width='80' height='25'>" + thiddenDMgenderStringX[i].value + "</td><td width='80' height='25'>N/A</td><td width='31' height='25'>&nbsp;</td><td width='31' height='25'>&nbsp;</td></tr></table></div></div>";
        reSt += tm;
    }
    //    alert(reSt);
    return reSt;
}

function getTempDependenString(checkVal) {
    //    var reStid = 'mx' + passport;
    // alert('---' + checkVal);
    //    var stn = document.getElementById(reStid).innerHTML;
    var hiddenDMgenderStringX = document.getElementsByName('hiddenDMgenderString');
    //    alert(hiddenDMgenderStringX.length);       
    var hiddenDPassportNoX = document.getElementsByName('hiddenDPassportNo');
    //     alert(hiddenDPassportNoX.length);       
    var hiddenDSurnameX = document.getElementsByName('hiddenDSurname');
    //         alert(hiddenDSurnameX.length);       
    var hiddenDOtherNamesX = document.getElementsByName('hiddenDOtherNames');
    //     alert(hiddenDOtherNamesX.length);       
    var hiddenDRealationShipX = document.getElementsByName('hiddenDRealationShip');
    //     alert(hiddenDRealationShipX.length);    
    var hiddenDGenderX = document.getElementsByName('hiddenDGender');
    //       alert(hiddenDGenderX.length);    
    var hiddenDDobDateX = document.getElementsByName('hiddenDDobDate');
    var hiddenDMemberNoX = document.getElementsByName('hiddenDMemberNo');

    //           alert(hiddenDDobDateX.length);    
    var reSt = "";
    var count = 0;
    // alert(checkVal);
    for (var i = 0;i < hiddenDMemberNoX.length;i++) {
        //        alert(hiddenDPassportNoX[i].value);        
        var checkPs = hiddenDMemberNoX[i].value.trim();
        // alert(checkPs);
        if (checkVal == checkPs) {
            count++;
            memberStr = "<div id='idDependentDiv" + count + "'><table border='0' cellpadding='0' cellspacing='5' width='562' style='table-layout:fixed'><input name='thiddenDMgenderString' id='thiddengenderString" + count + "' type='hidden' value='" + hiddenDMgenderStringX[i].value + "' /><input name='thiddenDPassportNo' id='thiddenDPassportNo" + t + "' type='hidden' value='" + hiddenDPassportNoX[i].value + "' /><input name='thiddenDSurname' id='thiddenDSurname" + count + "' type='hidden' value='" + hiddenDSurnameX[i].value + "' /><input name='thiddenDOtherNames'  id='thiddenDOtherNames" + count + "' type='hidden' value='" + hiddenDOtherNamesX[i].value + "' /><input name='thiddenDRealationShip' id='thiddenDRealationShip" + count + "' type='hidden' value='" + hiddenDRealationShipX[i].value + "' /><input name='thiddenDGender' id='thiddenDGender" + count + "' type='hidden' value='" + hiddenDGenderX[i].value + "' /><input name='thiddenDDobDate' id='thiddenDDobDate" + count + "' type='hidden' value='" + hiddenDDobDateX[i].value + "'/><col width='100'> <col width='200'> <col width='80'><col width='80'> <col width='51'> <col width='51'><tr align='left' valign='middle' class='inner_text_1'><td width='100' height='25'>" + hiddenDPassportNoX[i].value + "</td><td width='200' height='25'>" + hiddenDSurnameX[i].value + "</td><td width='80' height='25'>" + hiddenDDobDateX[i].value + "</td> <td width='80' height='25'>" + hiddenDMgenderStringX[i].value + "</td><td width='51' height='25'><a href='#' id='" + count + "' onclick='editDependent(this.id);'>Edit</a></td> <td width='51' height='25'><a href='#' onclick='deleteDependent(this.id);' id='" + count + "'>Remove</a></td></tr> </table></div>";
            reSt += memberStr;
        }
    }

    //    alert(stn);
    initializeDependentCounts(count);
    document.getElementById('idDependentDiv0').innerHTML = reSt;

    //    alert(reSt);
    return reSt;
}