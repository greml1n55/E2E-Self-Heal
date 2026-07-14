import React, { useState } from 'react';
import clsx from 'clsx';
import helpWantedData from '../../data/help-wanted.json';
import styles from './styles.module.css';

interface HelpWantedItem {
  title: string;
  description: string;
  issueUrl: string;
  area: string;
  difficulty: 'easy' | 'medium' | 'hard';
}

export default function HelpWantedBoard(): React.ReactNode {
  const [activeFilter, setActiveFilter] = useState<'All' | 'Frontend' | 'Backend'>('All');

  const filteredData = (helpWantedData as HelpWantedItem[]).filter((item) => {
    if (activeFilter === 'All') return true;
    return item.area.toLowerCase() === activeFilter.toLowerCase();
  });

  return (
    <div className={styles.boardContainer}>
      <div className={styles.filterWrapper}>
        <span className={styles.filterLabel}>Filter:</span>
        <div className={styles.filterButtons}>
          {(['All', 'Frontend', 'Backend'] as const).map((filter) => (
            <button
              key={filter}
              className={clsx(styles.filterButton, {
                [styles.activeFilter]: activeFilter === filter,
              })}
              onClick={() => setActiveFilter(filter)}
            >
              {filter}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.grid}>
        {filteredData.map((item, index) => {
          const diffClass =
            item.difficulty === 'easy'
              ? styles.badgeEasy
              : item.difficulty === 'medium'
              ? styles.badgeMedium
              : styles.badgeHard;

          return (
            <a
              key={index}
              href={item.issueUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.card}
            >
              <div className={styles.cardHeader}>
                <h3 className={styles.cardTitle}>{item.title}</h3>
                <div className={styles.badgeRow}>
                  <span className={clsx(styles.badge, styles.badgeArea)}>
                    {item.area}
                  </span>
                  <span className={clsx(styles.badge, diffClass)}>
                    {item.difficulty}
                  </span>
                </div>
              </div>
              <p className={styles.cardDescription}>{item.description}</p>
              <div className={styles.cardFooter}>
                <span>View Issue</span>
                <span className={styles.arrowIcon}>→</span>
              </div>
            </a>
          );
        })}
      </div>
    </div>
  );
}
