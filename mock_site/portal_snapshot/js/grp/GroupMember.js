/* 
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */
var memberCount = 0;
var memberDeletCount = 0;
var maxNoOfMembers = 0;
var edit = false;

function initializeMemberCounts(count) {
    //    alert(count);
    memberCount = count;
    memberDeletCount = count;
    if (count > 0) {
        setMemberDeatilsHeader();
        var strBut = "<input type='button' name='Submit' class='body_text_th' value='Change' onclick='validateMemberForm(this);'/>";
        document.getElementById('idSumfB').innerHTML = strBut;
        edit = true;
    }
    else {
        document.getElementById('idSumfB').innerHTML = '';
        edit = false;

    }
}

function onloadGroupMemberForm() {
    var mC = document.getElementById("idHMemberCount").value;
    var dC = document.getElementById("idHDependentCount").value;
    initializeMemberCounts(mC);
    initializeDependentCounts(dC);
    //    populateDependPassportValues();
    init('idMemberFormC');
    getParmList();

}

function populateDependPassportValues() {

    var xhiddenSurname = document.getElementsByName("hiddenSurname");
    var xhiddenPassportNo = document.getElementsByName("hiddenPassportNo");
    for (var xp = 0;xp < xhiddenPassportNo.length;xp++) {
        this.addPassport(xhiddenPassportNo[xp].value, (xhiddenSurname[xp].value + '-' + xhiddenPassportNo[xp].value));
    }

}

function addGroupMember(appType) {
    // alert("memberDeletCount "+memberDeletCount)
    // alert("maxNoOfMembers "+maxNoOfMembers)

    if (memberDeletCount < maxNoOfMembers) {
        var passportNo = document.getElementById("idPassportNo");
        var idReEnteredPassportNo = document.getElementById("idReEnteredPassportNo");
        var idHiddenPassOkX = document.getElementById("idHiddenPassOk");
        var surname = document.getElementById("idSurname");
        var otherNames = document.getElementById("idOthernames");
        var title = document.getElementById("idTitle");
        var nationality = document.getElementById("idNatinality");
        var vaccinationFlag = document.getElementById("idVaccinationFlag");
        var idtouristNo = document.getElementById("idtouristNo");
        var cob = document.getElementById("idCOB");
        var coa = document.getElementById("idCOA");
        var occupation = document.getElementById("idOccupation");
        //    var realationShip = document.getElementById("idRelationShip");
        var gender = document.getElementById("idGender");
        var dobStamp = document.getElementById("idDobDate");
        var idReEnteredDobDate = document.getElementById("idReEnteredDobDate");
        var passIssuStamp = document.getElementById("idPassIsueDate");
        var passExStamp = document.getElementById("idPassExpDate");
        var xconfTick = document.getElementById("idConfTick");
        var xhiddenQCodes = document.getElementsByName("hiddenQuestionCodes");
        var xhiddenVaccinationStatusInput = document.getElementsByName("hiddenVaccinationStatusInput");
        // var vaccinationFlag = document.getElementsByName("vaccinationFlag");
        // alert(vaccinationFlag);
        var genderString = "";

        var tempOk = true;

        if ((surname.value == null || surname.value == '' || surname.value.trim()=='') && tempOk) {
            alert(' Please enter Surname/Family Name');
            tempOk = false;
            surname.focus();
        }
        else {
            tempOk = validateName_OnChange(surname, 'Surname');

        }
        //alert('tempok'+tempOk);
        if (tempOk) {
            if (otherNames.value == null || otherNames.value == '' || otherNames.value.trim()=='') {
                tempOk = false;
                alert('Please enter Other/Given Names ');
                otherNames.focus();
            }
            else {
                tempOk = validateName_OnChange(otherNames, 'Other/Given Names');

            }
        }
        if (tempOk && (title.value == null || title.value == '' || title.value == '0X')) {
            tempOk = false;
            title.focus();
            alert('Please select Title');
        }
        if (tempOk && (dobStamp.value == null || dobStamp.value == '')) {
            tempOk = false;
            dobStamp.focus();
            alert('Please select Date of Birth');
        }

        if (tempOk) {
            if ((gender.value == null || gender == '' || gender.value == '0X')) {
                tempOk = false;
                gender.focus();
                alert('Please select Gender');
            }
            else {
                var theContents = document.getElementById('idGender')[document.getElementById('idGender').selectedIndex].text;
                genderString = theContents.trim();
            }
        }
        if (tempOk && (nationality.value == null || nationality.value == '' || nationality.value == '0X')) {
            tempOk = false;
            alert('Please select Nationality');
            nationality.focus();

        }

        if (tempOk && (cob.value == null || cob.value == '' || cob.value == '0X')) {
            tempOk = false;
            alert('Please select Country of Birth');
            cob.focus();
        }

        if (tempOk && (coa.value == null || coa.value == '' || coa.value == '0X')) {
            tempOk = false;
            alert('Please select a Country of Address');
            coa.focus();
        }

        if (tempOk && (occupation.value != null && occupation.value != '')) {
            ok = validatealphanumWithSpace_onChange(occupation, 'Occupation');
        }
        //        if (tempOk) {
        if (tempOk && (passportNo.value == null || passportNo.value == '' || idHiddenPassOkX == '0')) {
            alert('Please enter Passport Number');
            passportNo.focus();
            tempOk = false;
        }

        //        }
        if (tempOk && (passIssuStamp.value == null || passIssuStamp.value == '')) {
            tempOk = false;
            passIssuStamp.focus();
            alert('Please select Passport issued date');
        }

        if (tempOk && (passExStamp.value == null || passExStamp.value == '')) {
            tempOk = false;
            passExStamp.focus();
            alert('Please select Passport expiry date');
        }
        //    if ((realationShip.value == null || realationShip.value) == '0X' && tempOk) {
        //        tempOk = false;
        //        alert('Please select applicants relationship');
        //
        //    }
        //alert('tempOk = '+tempOk);
        if (tempOk) {
            tempOk = validateNoOfQuestionsChecked();
        }
        if (tempOk && !xconfTick.checked) {
            alert(' Please confirm your details');
            xconfTick.focus();
            tempOk = false;

        }

        var vaccinaion=vaccinationFlag.value;
        // var vaccinaion ='-';
        // if (tempOk && xhiddenVaccinationStatusInput && vaccinationFlag!=null) {
        //     // alert("test----1");
        //     if ((vaccinationFlag.value == null || vaccinationFlag.value == '' || vaccinationFlag.value.trim()=='') && tempOk) {
        //         alert(' Please Select Covid Vaccination status');
        //         tempOk = false;
        //         vaccinationFlag.focus();
        //     }else{
        //         vaccinaion=vaccinationFlag.value;
        //     }
        // }
        if (tempOk && idReEnteredPassportNo.value == "") {
            alert("Please Insert Value For \'Re Enter Passport No\' Field");
            idReEnteredPassportNo.focus();
            tempOk = false;
        }
        if (tempOk && idReEnteredPassportNo.value !== passportNo.value) {
            alert("Re-entered Passport No does not match the previous entered Passport No!");
            idReEnteredPassportNo.value = ''; // Clear the field
            idReEnteredPassportNo.focus();
            tempOk = false;
        }

        if (tempOk && idReEnteredDobDate.value == "") {
            alert("Please Insert Value For \'Re Enter Date Of Birth \' Field");
            idReEnteredDobDate.focus();
            tempOk = false;
        }
        if (tempOk && idReEnteredDobDate.value !== dobStamp.value) {
            alert("Re-entered Date Of Birth does not match the previous entered Date!");
            idReEnteredDobDate.value = ''; // Clear the field
            idReEnteredDobDate.focus();
            tempOk = false;
        }
        if (tempOk) {
            // alert("test----2");
            memberCount++;
            memberDeletCount++;
            var qustionsAns = "";
            var qCode = null;
            var vlrN = null;
            var vlrY = null;
            var qValue = "";

            for (var i = 0;i < xhiddenQCodes.length;i++) {
                qCode = xhiddenQCodes[i].value;
                vlrN = "vlrN" + qCode;
                if (document.getElementById(vlrN).checked) {
                    qValue = "0";
                }
                else {
                    vlrY = "vlrY" + qCode;
                    if (document.getElementById(vlrY).checked) {
                        qValue = "1";
                    }
                    else {

                    }

                }
                //            alert("selelcted= "+qValue);
                //            alert("passportNo= "+passportNo);
                //            alert("qCode= "+qCode);
                qustionsAns += "<input type='hidden' id='" + passportNo.value + '|' + qCode + "' name='otherDecQuesAns' value='" + passportNo.value + '|' + qCode + "|" + qValue + "'/>";
                //        alert( passportNo + '|' + qCode );
            }

            var depDivData = '';
            if (dependentDeletCount > 0) {
                //            depDivData = document.getElementById(dp).innerHTML;
                //            var temStr = depDivData.split(",");
                depDivData = getActualDependenString();
                //            alert(depDivData);
            }
            if (memberDeletCount == 1) {
                setMemberDeatilsHeader();
                var strBut = '';
                if (edit) {
                    strBut = "<input type='button' name='Submit' value='Change'  class='body_text_th' onclick='validateMemberForm(this);'/>";
                }
                else {
                    strBut = "<input type='button' name='Submit' value='Next'  class='body_text_th' onclick='validateMemberForm(this);'/>";
                }
                document.getElementById('idSumfB').innerHTML = strBut;
            }
            // alert("test----3");
            // alert("test----3"+vaccinationFlag.value);
            var memberStr = "<div id='idMembersDiv" + memberCount + "'>" + qustionsAns + "<table width='562' border='0' cellpadding='0' cellspacing='5' style='table-layout:fixed'>" +
                "<input name='hiddenMemberNo' id='hiddenMemberNo" + memberCount + "' type='hidden' value='" + memberCount + "' />" +
                "<input name='hiddenMgenderString' id='hiddengenderString" + memberCount + "' type='hidden' value='" + genderString + "' />" +
                "<input name='hiddenPassportNo' id='hiddenPassportNo" + memberCount + "' type='hidden' value='" + passportNo.value + "' />" +
                "<input name='hiddenReEnteredPassportNo' id='hiddenReEnteredPassportNo" + memberCount + "' type='hidden' value='" + idReEnteredPassportNo.value + "' />" +
                "<input name='hiddenSurname' id='hiddenSurname" + memberCount + "' type='hidden' value='" + surname.value + "' />" +
                "<input name='hiddenOtherNames'  id='hiddenOtherNames" + memberCount + "' type='hidden' value='" + otherNames.value + "' />" +
                "<input name='hiddenTitle' id='hiddenTitle" + memberCount + "' type='hidden' value='" + title.value + "' />" +
                "<input name='hiddenNationality' id='hiddenNationality" + memberCount + "' type='hidden' value='" + nationality.value + "' />" +
                "<input name='hiddenVaccinationFlag' id='hiddenVaccinationFlag" + memberCount + "' type='hidden' value='" + vaccinaion + "' />" +
                "<input name='idtouristNo' id='idtouristNo" + memberCount + "' type='hidden' value='" + idtouristNo + "' />" +
                "<input name='hiddenCob' id='hiddenCob" + memberCount + "' type='hidden' value='" + cob.value + "' />" +
                "<input name='hiddenCoa' id='hiddenCoa" + memberCount + "' type='hidden' value='" + coa.value + "' />" +
                "<input name='hiddenOccupation' id='hiddenOccupation" + memberCount + "' type='hidden' value='" + occupation.value + "' />" +
                "<input name='hiddenGender' id='hiddenGender" + memberCount + "' type='hidden' value='" + gender.value + "' />" +
                "<input name='hiddenDobDate' id='hiddenDobDate" + memberCount + "' type='hidden' value='" + dobStamp.value + "' />" +
                "<input name='hiddenReEnteredDobDate' id='hiddenReEnteredDobDate" + memberCount + "' type='hidden' value='" + idReEnteredDobDate.value + "' />" +
                "<input name='hiddenPassIssueDate' id='hiddenPassIssueDate" + memberCount + "' type='hidden' value='" + passIssuStamp.value + "' />" +
                "<input name='hiddenPassExDate' id='hiddenPassExDate" + memberCount + "' type='hidden' value='" + passExStamp.value + "'/><col width=50> <col width='80'> <col width='130'><col width='80'> <col width='80'> <col width='80'><col width='31'> <col width='31'> <tr align='left' valign='middle' class='inner_text_1'><td width='50' height='25'>Member</td><td width='80' height='25'>" + passportNo.value + "</td><td width='130' height='25'>" + surname.value + "</td><td width='80' height='25'>" + dobStamp.value + "</td> <td width='80' height='25'>" + genderString + "</td><td width='80' height='25'>" + passIssuStamp.value + "</td><td width='31' height='25'><a href='#' id='" + memberCount + "' onclick='editMember(this.id);'>Edit</a></td><td width='31' height='25'><a href='#' onclick='deleteMember(this.id);' id='" + memberCount + "'>Remove</a></td></tr></table>" + depDivData + "</div>";
            // alert(memberStr);
            document.getElementById('idMembersDiv0').innerHTML += memberStr;
            //  this.addPassport(passportNo.value, (surname.value + '-' + passportNo.value));
            if (memberDeletCount == maxNoOfMembers) {
                alert('You have reached the maximum number of members per application,you wont be able to add more after this');
            }
            resetFeilds();
        }

    }
    else {
        alert('You have reached the maximum number of members per application,you cannot add more');
        resetFeilds();
    }

}

function deleteMember(id) {
    var messg = "Are you sure to delete this member and relevent child details??";
    if (confirm(messg)) {
        var tem = "idMembersDiv" + id;
        //    deletePasaportDependent(document.getElementById(("hiddenPassportNo" + id)).value);
        document.getElementById(tem).innerHTML = '';
        memberDeletCount--;
        initializeDependentCounts(0);
        if (memberDeletCount == 0) {
            document.getElementById('idMembersDiv0').innerHTML = '';
            document.getElementById('idMemHedDiv').innerHTML = '';
            document.getElementById('idSumfB').innerHTML = '';
        }
    }
}

function editMember(id) {
    //      alert(id);
    var editM = document.getElementById("idHiddenMemEdit").value;
    var editMessage = 'There is a member detail not yet saved,do you want to discard these details?';
    if (editM == '0' || (ok > 0 && confirm(editMessage))) {
        document.getElementById("idHiddenMemEdit").value = id;
        document.getElementById("idPassportNo").value = document.getElementById(("hiddenPassportNo" + id)).value.trim();;
        document.getElementById("idReEnteredPassportNo").value = document.getElementById(("hiddenReEnteredPassportNo" + id)).value.trim();
        document.getElementById("idNatinality").value = document.getElementById("hiddenNationality" + id).value.trim();
        document.getElementById("idVaccinationFlag").value = document.getElementById("hiddenVaccinationFlag" + id).value.trim();
        document.getElementById("idSurname").value = document.getElementById("hiddenSurname" + id).value;
        document.getElementById("idOthernames").value = document.getElementById("hiddenOtherNames" + id).value;
        document.getElementById("idTitle").value = document.getElementById("hiddenTitle" + id).value;
        document.getElementById("idCOB").value = document.getElementById("hiddenCob" + id).value;
        document.getElementById("idCOA").value = document.getElementById("hiddenCoa" + id).value;
        document.getElementById("idOccupation").value = document.getElementById("hiddenOccupation" + id).value;
        document.getElementById("idGender").value = document.getElementById("hiddenGender" + id).value;
        document.getElementById("idDobDate").value = document.getElementById("hiddenDobDate" + id).value;
        document.getElementById("idReEnteredDobDate").value = document.getElementById("hiddenReEnteredDobDate" + id).value;
        document.getElementById("idPassIsueDate").value = document.getElementById("hiddenPassIssueDate" + id).value;
        document.getElementById("idPassExpDate").value = document.getElementById("hiddenPassExDate" + id).value;
        var memNo = document.getElementById("hiddenMemberNo" + id).value;

        document.getElementById("idHiddenPassOk").value = '1';
      //  document.getElementById('idLodingPassPort').innerHTML = '<font color="#009900"><b>Passport Number has been successfully verified.</b></font>';
        //    alert('1'); 
          document.getElementById('idLodingPassPort').innerHTML = '';
        makeQuesutionsSelected();
        getTempDependenString(memNo);
        //    alert('2');
        //    deletePasaportDependent(document.getElementById(("hiddenPassportNo" + id)).value);
        var tem = "idMembersDiv" + id;
        //    document.getElementById("idPassportNo").value
        document.getElementById(tem).innerHTML = '';
        memberDeletCount--

        if (memberDeletCount == 0) {
            document.getElementById('idMembersDiv0').innerHTML = '';
            document.getElementById('idMemHedDiv').innerHTML = '';
            document.getElementById('idSumfB').innerHTML = '';
        }

    }
}

function makeQuesutionsSelected() {
    //    alert('1');
    var passport = document.getElementById("idPassportNo").value;
    var hiddenQCodes = document.getElementsByName("hiddenQuestionCodes");
    //    alert(hiddenQCodes.length);
    var idString = null;
    var qCode = null;
    //alert(questionCount);    
    for (var i = 0;i < hiddenQCodes.length;i++) {
        //        alert('i===' + i);
        qCode = hiddenQCodes[i].value;
        idString = passport + '|' + qCode;
        //        alert(idString);
        var com = document.getElementById(idString);
        if (com != null) {
            var valX = com.value.split("|")[2];
            //            alert('valX==' + valX);
            if (valX == 0) {
                document.getElementById("vlrN" + qCode).checked = true;
                document.getElementById("vlrY" + qCode).checked = false;
            }
            else {
                document.getElementById("vlrY" + qCode).checked = true;
                document.getElementById("vlrN" + qCode).checked = false;
            }

        }

    }
}

function validateQuestions(object) {

    var passport = document.getElementById("idPassportNo").value;
    if (passport != null && passport != '') {
        if (object.value != null && object.value == 1) {
            object.checked = false;
            alert('You are not eligible for visa');

        }
    }
    else {
        object.checked = false;
        alert('Please fill the member details prior selecting the declarations');

    }

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

function resetFeilds() {
    document.getElementById("idSurname").value = '';
    document.getElementById("idOthernames").value = '';
    document.getElementById("idTitle").value = '0X';
    document.getElementById("idNatinality").value = '0X';
    document.getElementById("idCOB").value = '0X';
    document.getElementById("idCOA").value = '0X';
    document.getElementById("idOccupation").value = '';
    //    document.getElementById("idRelationShip").value = '0X';
    document.getElementById("idGender").value = '0X';
    // document.getElementById("idVaccinationFlag").value = '0X';
    document.getElementById("idDobDate").value = '';
    document.getElementById("idReEnteredDobDate").value = '';
    document.getElementById("idPassIsueDate").value = '';
    document.getElementById("idPassExpDate").value = '';
    document.getElementById("idConfTick").checked = false;
    var hiddenQCodes = document.getElementsByName("hiddenQuestionCodes");
    document.getElementById('idLodingPassPort').innerHTML = '';
    document.getElementById('idPassportNo').value = '';
    document.getElementById('idReEnteredPassportNo').value = '';
    document.getElementById("idHiddenMemEdit").value = '0';
    //  alert(hiddenQCodes+"resetting");
    var idString = null;
    var code = null;
    for (var i = 0;i < hiddenQCodes.length;i++) {
        code = hiddenQCodes[i].value;
        idString = "vlrN" + code;
        //        alert(idString);
        var comN = document.getElementById(idString);
        comN.checked = false;
        idString = "vlrY" + code;
        //         alert(idString);
        var comY = document.getElementById(idString);
        comY.checked = false;
    }

    document.getElementById('idDepHedDiv').innerHTML = '';
    document.getElementById('idDependentDiv0').innerHTML = '';

    initializeDependentCounts(0);
    enabelDisableDependent(0);
}

function validateMemberForm(button) {
    var ok = true;
    button.disabled = true;

    var editM = document.getElementById("idHiddenMemEdit").value;
    // alert(editM);
    var editMessage = 'There is a member detail not yet saved,do you want to discard these details?';
    if (editM == '0' || (ok > 0 && confirm(editMessage))) {

        if (memberDeletCount == 0) {
            ok = false;
            alert('Sorry, you cannot continue without any members');
            button.disabled = false;
        }
        else {
//            stopCount();
            button.form.submit();
        }
    }else{
    
     button.disabled = false;
    }
}

function setMemberDeatilsHeader() {
    var str = "<table height='30' border='0' cellpadding='0' cellspacing='5' width='562' style='table-layout:fixed'><col width=50> <col width='80'> <col width='130'><col width='80'> <col width='80'> <col width='80'><col width='31'> <col width='31'> <tr align='center'' valign='middle'' class='textHeadingBlack'><th width='50' height='30' class='TBline_2'> Member-Child </th><th width='80' height='30' class='TBline_2'>Passport  No</th><th width='130'  height='30' class='TBline_2'>Surname</th><th width='80' height='30' class='TBline_2'>Date of Birth</th><th width='80' height='30' class='TBline_2'>Gender</th><th width='80' height='30' class='TBline_2'> Passport Issued date </th><th width='31' height='30' class='TBline_2'>Edit</th> <th width='31' height='30' class='TBline_2'>Remove</th></tr></table>";
    document.getElementById('idMemHedDiv').innerHTML = str;

}