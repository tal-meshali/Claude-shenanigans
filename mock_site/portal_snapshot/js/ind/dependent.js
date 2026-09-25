function ChangeChild() {
    if (document.form1.redDep.checked == true) {
        EnableDep()
    }
    else {
        DisableDep()
    }
}

function EnableDep() {
    document.getElementById('dSurname').disabled = false;
    document.getElementById('dOthernames').disabled = false;
    document.getElementById('dDobDate').disabled = false;
    document.getElementById('dGender').disabled = false;
    document.getElementById('relationship').disabled = false;
    document.getElementById('btnAddDep').disabled = false;
    document.getElementById('redDep').checked = true;

}

function DisableDep() {
    document.getElementById('dSurname').disabled = true;
    document.getElementById('dOthernames').disabled = true;
    document.getElementById('dDobDate').disabled = true;
    document.getElementById('dGender').disabled = true;
    document.getElementById('relationship').disabled = true;
    document.getElementById('btnAddDep').disabled = true;
    document.getElementById('redDep').checked = false;

}

var varSpnId = 1;

function checkDepDate() {
    //var bdate = Date.parse(document.getElementById('dDobDate').value);
    var bdate = document.getElementById('dDobDate').value;//22-12-2011
    var today = new Date();
    var age = today.getFullYear() - bdate.substring(6, 10);
    if (today.getMonth() < bdate.substring(3, 5) || (today.getMonth() == bdate.substring(3, 5) && today.getDate() < bdate.substring(0, 2))) {
        age--;
    }
    if (age >= 16) {
        alert("Maximum upper age limit is 16 for a child");
        return false;
    }
    else if (age >= 12) {
        var r = confirm("Child age between 12-16 years will be charged the VISA fee\n Do you want to proceed ?")
        if (r == true) {
            //addRowNow();
            return true;
        }
        else {
            //emptyElements();
            return false;
        }
    }
    else {
        //addRowNow();
        return true;
    }

}

function addRow() {
    var Name = document.getElementById('dSurname').value;
    var OthName = document.getElementById('dOthernames').value;
    var BDate = document.getElementById('dDobDate').value;
    var reEnteredDDobDate = document.getElementById('reEnteredDDobDate').value;
    var Gender = document.getElementById('dGender').value;
    //var PassportNo = document.getElement('dPassportno').value;
    var RelationShip = document.getElementById('relationship').value;
    //added the follwings
    if (Name.trim() == '') {
        alert("Please Insert Family/Surname of Child");
        document.getElementById('dSurname').focus();
        return false;
    }

    if (OthName.trim() == '') {
        alert("Please Insert Other/Given Names of Child");
        document.getElementById('dOthernames').focus();
        return false;
    }

    if (BDate == '') {
        alert("Please Insert Date of Birth of Child");
        document.getElementById('dDobDate').focus();
        return false;
    }
    if (reEnteredDDobDate == '') {
        alert("Please Insert Re-entered Date of Birth of Child");
        document.getElementById('reEnteredDDobDate').focus();
        return false;
    }
    if (reEnteredDDobDate !== BDate) {
        alert("Re-entered Date of Birth does not match the previous entered Date of Birth!");
        document.getElementById('reEnteredDDobDate').focus();
        return false;
    }
    if (!chkDepBDate(BDate)) {
        alert("Please Insert Date of Birth of Child correctly");
        document.getElementById('dDobDate').value = "";
        document.getElementById('dDobDate').focus();
        return false;
    }
    if (Gender == '') {
        alert("Please select Gender of Child");
        document.getElementById('dGender').focus();
        return false;
    }
    if (RelationShip == '') {
        alert("Please select Relationship of Child");
        document.getElementById('relationship').focus();
        return false;
    }

    //if(checkDepDate()) {
    var valId = "Val" + varSpnId;
    document.getElementById("divDep").innerHTML = document.getElementById("divDep").innerHTML + "<span id='spn" + varSpnId + "'><TABLE width='571' height='30' border='0' cellpadding='0' cellspacing='5' id='dataTable'><TR class='menutextthbl'><TD width='20'><input type='hidden' name='spnNos' value='spnDepNo" + varSpnId + "'><span id='spnDepNo" + varSpnId + "'>1</span></TD><TD width='99'> " + Name + "</TD><TD width='96'>" + OthName + " </TD><TD width='106'>" + BDate + "</TD><TD width='59'>" + Gender + "</TD><TD width='82'>" + RelationShip + "</TD><TD width='45'><a href='#'  onclick='editRow(\"" + varSpnId + "\");'>Edit</a></TD><TD width='64'><a href='#'  onclick='deleteRow(\"" + varSpnId + "\");'>Remove</a><input type='hidden' value='" + Name + "|" + OthName + "|" + BDate + "|" + Gender + "|" + RelationShip + "' name='depValues' id='" + valId + "'></TD></TR></TABLE></span>"
    varSpnId++;
    emptyElements();
    setRowNo();
    // }
}

function setRowNo() {
    try {
        var i = 0;
        //alert(document.form1.spnNos.value);
        //alert(document.form1.spnNos.length);
        while (document.form1.spnNos.length > i) {
            document.getElementById(document.form1.spnNos[i].value).innerHTML = i + 1;
            i++;
        }
    }
    catch (e) {
    }
}

function emptyElements() {
    document.getElementById('dSurname').value = "";
    document.getElementById('dOthernames').value = "";
    document.getElementById('dDobDate').value = "";
    document.getElementById('reEnteredDDobDate').value = "";
    document.getElementById('dGender').value = "";
    document.getElementById('relationship').value = "";
}

function editRow(spnId) {
    var valId = "Val" + spnId;
    var vaLues = document.getElementById(valId).value;
    var ary = vaLues.split("|");
    document.getElementById('dSurname').value = ary[0];
    document.getElementById('dOthernames').value = ary[1];
    document.getElementById('dDobDate').value = ary[2];
    document.getElementById('dGender').value = ary[3];
    document.getElementById('relationship').value = ary[4];
    try {
        var valId = "spn" + spnId;
        document.getElementById(valId).innerHTML = "";
        EnableDep();
        document.getElementById('relationship').focus();        
    }
    catch (ed) {
    }
    setRowNo();
}

function deleteRow(spnId) {
    try {
        var r = confirm("Are You sure to remove the child ?")
        if (r == true) {

            var valId = "spn" + spnId;
            document.getElementById(valId).innerHTML = "";
            setRowNo();
        }
    }
    catch (e) {
    }
}

function chkDepBDate(depbday) {
    var currentTime = new Date();
    var month = currentTime.getMonth() + 1;
    var day = currentTime.getDate();
    var year = currentTime.getFullYear();
    currentTime = month + "-" + day + "-" + year;
    var curdate = Date.parse(currentTime);
    var bdate = Date.parse(depbday);
    if (bdate > curdate)
        return false;
    else 
        return true;
}