import numpy as np
import pandas as pd
from fuzzywuzzy import process
import re

@pd.api.extensions.register_dataframe_accessor("pr")
class PeerReviewAccessor():
    """
    set of tools for quickly processing survey responses
    """
    def __init__(self, df):
        self.df = df

    @staticmethod
    def _validate(df):
        """
        ensure dataframe format implies a single student is asked for
        multiple identifiers, i.e. a team. return the identifier string
        """
        questions = df.columns.difference(
            df.select_dtypes(np.number).columns
        ).get_level_values(-1)
        
        ident1 = ['email address' in s for s in questions.to_list()]
        ident2 = ['name' in s for s in questions.to_list()]

        if sum(ident1) >= 2:
            return 'email address'
        elif sum(ident2) >= 2:
            return 'name'
        else:
            raise AttributeError(
                'peer reviews must have 2 or more identifier columns'
            )

    def _make_long(self):
        ldf = self.df.melt(
            id_vars = self.df.columns.difference(
                self.df.columns[
                    self.df.columns.get_level_values(-1).str.contains(
                        self.id_string
                    )
                ]).to_list(),
            value_name = 'name',
            var_name = ["q_name", 'author']
        ).drop('q_name', axis=1)

        ldf = ldf.dropna(subset=['name'])

        ldf['author'] = ldf['author'].apply(
            lambda x: 'your purdue email'.casefold() in x.casefold()
        )

        ldf = ldf.set_index(ldf.iloc[:, [0,-3,-2,-1]].columns.to_list())
        ldf.index.names = ['section', 'explanation', 'author', 'name']
        ldf = ldf.mean(axis=1)
        ldf = ldf.reset_index()
        ldf = ldf.rename(columns={0: 'rating'})

        return ldf

    def summarize(self, id_col):
        sdf = self.df.get_long(id_col).groupby('name').apply(
            column_aware_aggregator
        ).reset_index(
            names=['name', 'drop']
        ).drop('drop', axis=1)

        sdf['name'] = sdf.name.str.casefold()

        return sdf

def normalize_names(ldf, score_threshold = 90):
    """
    finds all similar names in ldf and makes them the same.

    Levenshtein similarity score_threshold set at 90 by default, for emails
    for human names, use ~80
    """
    inspected = []
    for i, row in ldf.iterrows():
        matches = process.extract(row['name'], ldf['name'].to_dict(), limit=5)
        idxs = [idx for name, score, idx in matches if score >= score_threshold]
        if i in inspected:
            continue
        else:
            inspected += idxs
            for idx in idxs:
                ldf.at[idx, 'name'] = matches[0][0]
    return ldf

def student_metric_aggregate(df):
    breakpoint()
    section = df.section.str.split('-').str[0][df['author'] == True] if (
        True in df['author'].to_list()
    ) else pd.Series(
        'did not submit (' + df.section.str.split('-').str[0].unique().sum() + ')'
    )
    section.name = 'section'
    section = section.reset_index(drop=True)
    # every student should be an author once, but some don't submit, if so, mark them
    explanation = pd.Series(
        " ".join(df.explanation[df.explanation.notna()].to_list())
    ) if (
        True in df.explanation.notna().to_list()
    ) else pd.Series([None])
    explanation.name = 'explanation'
    explanation = explanation.reset_index(drop=True)
    # students review eachother and themselves, just collect all reviews from a student's group
    author = pd.Series(
        df.author[df.explanation.notna()].any()
    ) if (
        True in df.explanation.notna().to_list()
    ) else pd.Series(False)
    author.name = 'author'
    author = author.reset_index(drop=True)
    # if this student was reviewed, it will show up. if they did not write any reviews, author will be false
    rating = pd.Series(df.rating.mean())
    rating.name = 'rating'
    rating = rating.reset_index(drop=True)
    test = pd.concat([section, explanation, author, rating], axis=1)
    return test
