#!/bin/bash

# Schema Changes Test Runner
# Validates all schema changes are working correctly

echo "=================================================="
echo "Schema Changes Verification Test Suite"
echo "=================================================="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Check migrations
echo -e "\n${YELLOW}Step 1: Checking migrations...${NC}"
python manage.py migrate --check
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All migrations are applied${NC}"
else
    echo -e "${RED}✗ Migrations check failed${NC}"
    exit 1
fi

# Step 2: Run schema validation tests
echo -e "\n${YELLOW}Step 2: Running schema validation tests...${NC}"
python manage.py test schema_validation_tests -v 2
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Schema validation tests passed${NC}"
else
    echo -e "${RED}✗ Schema validation tests failed${NC}"
    exit 1
fi

# Step 3: Run curriculum tests
echo -e "\n${YELLOW}Step 3: Running curriculum tests...${NC}"
python manage.py test curriculum.tests -v 2
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Curriculum tests passed${NC}"
else
    echo -e "${RED}✗ Curriculum tests failed${NC}"
    exit 1
fi

# Step 4: Run generators tests
echo -e "\n${YELLOW}Step 4: Running generators tests...${NC}"
python manage.py test generators.tests -v 2
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Generators tests passed${NC}"
else
    echo -e "${RED}✗ Generators tests failed${NC}"
    exit 1
fi

# Step 5: Summary
echo -e "\n${GREEN}=================================================="
echo "✓ ALL SCHEMA CHANGES VERIFIED AND WORKING"
echo "==================================================${NC}"

echo -e "\n${GREEN}Summary:${NC}"
echo "✓ User roles simplified (admin/member)"
echo "✓ SourceFile with file, file_size, page_count"
echo "✓ LessonSource with start_page/end_page validation"
echo "✓ QuestionType seeded (mcq, tf, short_answer)"
echo "✓ GenerationRequest with user, project, M2M lessons/types"
echo "✓ GeneratedQuestion with question_type FK"
echo "✓ All migrations applied successfully"
echo "✓ All tests passing"

echo -e "\n${YELLOW}Next steps:${NC}"
echo "1. Deploy to production"
echo "2. Monitor Celery workers"
echo "3. Test API endpoints with real frontend"
echo "4. Set up monitoring and logging"
