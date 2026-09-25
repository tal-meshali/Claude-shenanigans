/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 * This java script used to validate the front end in both individual and group jsps.
 */
//this return the asciil value of character
function validateDate(comp, lessDate, moreDate, message) {

    //    alert('com= '+comp );
    //    alert('lessDate= '+lessDate );
    //     alert('moreDate= '+moreDate );
    //     alert('message= '+message );
    //    var lDate = Date.parse(lessDate)
    //    var fDate = Date.parse(moreDate)
    //  alert(fDate);
    if (lessDate > moreDate) {
        alert(message);
        comp.value = '';
        comp.focus();
        return false;
    }
    else {
        //checkAllManFiled();
        return true;
    }
}

//Convert the given elment value to upper case
//function convertToUpperCase(x)///upperCase(x)
//{
//    var y = document.getElementById(x).value;
//    document.getElementById(x).value = y.toUpperCase();
//}
//this disable the copy paste function in UI.
function disablecopypaste()//nocopypaste(e,obj)
{
    var msg = "Sorry, this functionality is disabled.";
    alert(msg);
    return false;
}

// this is used to validate surname/family name & other/given names allows Alphabet & "'".
function validateName(obj) {
    //check Surname/Family name,Other /given names  replace checkNumberone in this fields
    var strPass = obj.value;
    var strLength = strPass.length;
    var lchar = obj.value.charAt((strLength) - 1);
    var cCode = getAsciiVal(lchar);
    if ((cCode > 64 && cCode < 91) || (cCode > 96 && cCode < 123) || cCode == 39 || cCode == 32) {
    }
    else {
        var myNumber = obj.value.substring(0, (strLength) - 1);
        obj.value = myNumber;
    }
    return false;
}

// this is used to validate surname/family name & other/given names onchange event
function validateName_OnChange(obj, val) {
    //check Surname/Family name,Other /given names  replace checkNumberone in this fields
    var strPass = obj.value;
    for (var j = 0;j < strPass.length;j++) {
        var cCode = getAsciiVal(strPass.charAt(j));

        if ((cCode > 64 && cCode < 91) || (cCode > 96 && cCode < 123) || cCode == 39 || cCode == 32) {

        }
        else {
            alert("Invalid " + val);
            document.getElementById(obj.id).value = '';
            return false;
        }
    }
    return false;
}

function validatealphanumWithSpace_onChange(obj, val) {
    var strPass = obj.value;
    for (var j = 0;j < strPass.length;j++) {
        var cCode = getAsciiVal(strPass.charAt(j));
        if ((cCode > 47 && cCode < 58) || (cCode > 64 && cCode < 91) || (cCode > 96 && cCode < 123 || cCode == 32)) {
        }
        else {
            alert("Invalid " + val);
            document.getElementById(obj.id).value = '';
            document.getElementById(obj.id).focus();
            return false;
        }
    }
    return true;

}
//check occupation,port of depature,comapny name,fianl destination
function validatealphanumWithSpace(obj) {
    var strPass = obj.value;
    var strLength = strPass.length;
    var lchar = obj.value.charAt((strLength) - 1);
    var cCode = getAsciiVal(lchar);
    if ((cCode > 47 && cCode < 58) || (cCode > 64 && cCode < 91) || (cCode > 96 && cCode < 123) || cCode == 32) {
    }
    else {
        var myNumber = obj.value.substring(0, (strLength) - 1);
        obj.value = myNumber;
    }

    return false;
}

//check occupation,port of depature,comapny name,fianl destination on change
function validatealphanumWithSpace_onChange(obj, val) {
    var strPass = obj.value;
    var ok = true;
    if (strPass != null && strPass != '') {
        for (var j = 0;j < strPass.length;j++) {
            var cCode = getAsciiVal(strPass.charAt(j));
            if ((cCode > 47 && cCode < 58) || (cCode > 64 && cCode < 91) || (cCode > 96 && cCode < 123 || cCode == 32)) {
                ok = true;
            }
            else {
                alert("Invalid " + val);
                obj.value = '';
                ok = false;
                obj.focus();
                break;
            }
        }
    }
    return ok;

}

//this is used to validate alphaNumeric values .used in pasport number,airline/vessel,flight/vessel number,zip code
function validatealphanum(obj) {
    var strPass = obj.value;
    var strLength = strPass.length;
    var lchar = obj.value.charAt((strLength) - 1);
    var cCode = getAsciiVal(lchar);
    if ((cCode > 47 && cCode < 58) || (cCode > 64 && cCode < 91) || (cCode > 96 && cCode < 123)) {
    }
    else {
        var myNumber = obj.value.substring(0, (strLength) - 1);
        obj.value = myNumber;
    }

    return false;
}

//this is used to validate alphaNumeric values onchange event .used in pasport number,zip code,airline/vessel,flight/vessel number
function validatealphanum_onChange(obj, val) {
    var strPass = obj.value;
    for (var j = 0;j < strPass.length;j++) {
        var cCode = getAsciiVal(strPass.charAt(j));
        if ((cCode > 47 && cCode < 58) || (cCode > 64 && cCode < 91) || (cCode > 96 && cCode < 123)) {
        }
        else {
            alert("Invalid " + val);
            document.getElementById(obj.id).value = '';
            return false;
        }
    }
    return true;

}

//this is used to validate email field characters.alphanumeric permitted,additionally "@","."and "_" permitted
function checkEmailCharacters(obj) {
    ////send object as parameter //checkNumberfr
    var strPass = obj.value;
    var strLength = strPass.length;
    var lchar = obj.value.charAt((strLength) - 1);
    var cCode = getAsciiVal(lchar);
//    if (cCode == 45) {
//        alert(cCode);
//    }
    if (cCode == 45 || (cCode > 47 && cCode < 58) || (cCode > 64 && cCode < 91) || (cCode > 96 && cCode < 123) || cCode == 64 || cCode == 46 || cCode == 95) {

    }
    else {
        var myNumber = obj.value.substring(0, (strLength) - 1);
        obj.value = myNumber;
    }
    return false;
}

//validate email format onchange event
function validateEmail(obj) {
    //checkemail
    var str = obj.value;
    var filter = /^([-]?[\w-]+(?:\.[\w-]+)*)@((?:[\w-]+\.)*\w[\w-]{0,66})\.([a-z]{2,6}(?:\.[a-z]{2})?)$/i;
    if (filter.test(str))
        testresults = true;
    else {
        alert("Please input a valid email address!");
        document.getElementById(obj.id).value = '';
        testresults = false;
    }
    return (testresults);
}

//validate two email fields matches on onchange event
function indValidateReEnteredEmail(obj, emailFieldId) {
    var email = document.getElementById(emailFieldId).value; // Get original email value
    var reEnterEmail = obj.value; // Get re-entered email value
    var ok = true; // Default to true

    if (reEnterEmail !== '') {
        if (reEnterEmail !== email) {
            alert("Re-entered email does not match the previous entered email!");
            obj.value = ''; // Clear the field
            obj.focus(); // Focus back to re-enter email field
            ok = false;
        }
    }
    return ok;
}

//this is used to validate telephone number,mobile number & fax number.numeric charcters and plus sign allowed.
function validateContactNumber(obj) {
    ////send object as parameter  //checkNumber for tel,mobile,fax
    var strPass = obj.value;
    var strLength = strPass.length;
    var lchar = obj.value.charAt((strLength) - 1);
    var cCode = getAsciiVal(lchar);
    if ((cCode > 47 && cCode < 58) || cCode == 43) {
        if ((cCode > 47 && cCode < 58)) {
        }
        else {
            if ((cCode == 43 && strLength == 1)) {
            }
            else {
                var myNumber = obj.value.substring(0, (strLength) - 1);
                obj.value = myNumber;
            }
        }
    }
    else {
        var myNumber2 = obj.value.substring(0, (strLength) - 1);
        obj.value = myNumber2;
    }
    return false;
}

//this is used to validate telephone number,mobile number & fax number.numeric charcters on chnage event
function validateContactNumber_onChange(obj, val) {
    var strPass = obj.value;
    for (var j = 0;j < strPass.length;j++) {
        var cCode = getAsciiVal(strPass.charAt(j));
        if ((cCode > 47 && cCode < 58) || cCode == 43) {
            if ((cCode > 47 && cCode < 58)) {
            }
            else {
                if ((cCode == 43 && j == 0)) {
                }
                else {
                    alert("Invalid " + val);
                    document.getElementById(obj.id).value = '';
                    return false;
                }
            }
        }
        else {
            alert("Invalid " + val);
            document.getElementById(obj.id).value = '';
            return false;
        }
    }
    return false;

}

//count  text characters element remaining in text area feild
//this is used to ignore "> and < characters".all the others are allowed
function validateCharacter(obj) {
    var strPass = obj.value;
    var strLength = strPass.length;
    var lchar = obj.value.charAt((strLength) - 1);
    var cCode = getAsciiVal(lchar);
    if (cCode == 60 || cCode == 62) {
        var myNumber = obj.value.substring(0, (strLength) - 1);
        obj.value = myNumber;
    }
    else {

    }
    return false;
}

function validateCharacterAdrress(obj) {
    var strPass = obj.value;
    var strLength = strPass.length;
    var lchar = obj.value.charAt((strLength) - 1);
    var cCode = getAsciiVal(lchar);
    var ok = true;

    if (strPass != null && strPass != '') {
        if (cCode == 60 || cCode == 62) {
            var myNumber = obj.value.substring(0, (strLength) - 1);
            obj.value = myNumber;
            obj.focus();
            ok = false;
        }
    }
    return ok;
}

//this is used to ignore "> and < characters" on change event.all the others are allowed
function validateCharacterAdrress_Onchange(obj, val) {
    //alert('1');
    var strPass = obj.value;
    var ok = true;
    for (var j = 0;strPass != null && strPass != '' && j < strPass.length;j++) {
        var cCode = getAsciiVal(strPass.charAt(j));
        if (cCode == 60 || cCode == 62) {
            alert("Invalid " + val);
            obj.value = '';
            obj.focus();
            ok = false;
            break;
        }

    }
    return ok;
}

//this is used to ignore "> and < characters" on change event.all the others are allowed
function validateCharacter_onChange(obj, val) {
    var strPass = obj.value;
    for (var j = 0;j < strPass.length;j++) {
        var cCode = getAsciiVal(strPass.charAt(j));

        if (cCode == 60 || cCode == 62) {
            alert("Invalid " + val);
            obj.value = '';
            obj.focus();
            return false;
        }
        else {

        }
    }
    return false
}

function validateNumber(val) {
    ////send object as parameter  //checkNumber
    var strPass = val.value;
    var strLength = strPass.length;
    var lchar = val.value.charAt((strLength) - 1);
    var cCode = getAsciiVal(lchar);

    if ((cCode > 47 && cCode < 58)) {

    }
    else {

        var myNumber = val.value.substring(0, (strLength) - 1);
        val.value = myNumber;
    }
    return false;
}

function validateDateDiff(date1, date2, val) {
    var dateg = Date.parse(date1);
    var datel = Date.parse(date2);
    if (datel > dateg) {
        if (val == "passport") {
            alert("Arrival date less than Passport Issued date");
            return false;
        }
    }
    return true;
}

//This is used to block autofill and copy-paste
let previousValues = {};
function limitInput(input) {
    const fieldId = input.id;
    console.log("IndValidateBusinessUI | limitInput | start >>>>>>>>>>")
    if (!previousValues.hasOwnProperty(fieldId)) {
        previousValues[fieldId] = "";
    }

    const currentValue = input.value;

    if (currentValue.length - previousValues[fieldId].length > 1) {
        input.value = previousValues[fieldId];
    } else {
        previousValues[fieldId] = currentValue;
    }
    console.log("IndValidateBusinessUI | limitInput | end <<<<<<<<<<<<")
}