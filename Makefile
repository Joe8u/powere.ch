
.PHONY: survey-all survey-clean

survey-all:
	./scripts/rebuild_survey_processed.sh

survey-clean:
	rm -f data/survey/processed/question_*.csv
