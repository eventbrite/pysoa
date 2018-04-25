#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TMP_FILE="$DIR/_temp_test_plan.rst"
FILE="$DIR/testing.rst"
LEAD='^\.\. BEGIN AUTO-GENERATED TEST PLAN DOCUMENTATION$'
TAIL='^\.\. END AUTO-GENERATED TEST PLAN DOCUMENTATION$'

echo "" > $TMP_FILE
python -c "import pysoa.test.plan; print(pysoa.test.plan.__doc__.strip(' \\r\\n'))" >> $TMP_FILE
echo "" >> $TMP_FILE

sed -i ".bak" -e "/$LEAD/,/$TAIL/{ /$LEAD/{p; r $TMP_FILE
        }; /$TAIL/p; d; }"  $FILE

rm $TMP_FILE
rm "${FILE}.bak"

echo "Test plan documentation updated in $FILE."
